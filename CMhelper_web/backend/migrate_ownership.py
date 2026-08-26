import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

# load .env first so DATABASE_URL is available
load_dotenv()

# We need to import our database components
from app.database import engine, SessionLocal
from app import crud, models
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    logger.info("Starting Customer Ownership Migration...")

    # Determine if we are on SQLite or PostgreSQL
    is_sqlite = engine.url.drivername.startswith("sqlite")

    with engine.connect() as conn:
        # Check if company_id column exists
        has_company_id = False
        has_assigned_user_id = False
        
        if is_sqlite:
            res = conn.execute(text("PRAGMA table_info(customers)")).fetchall()
            cols = [row[1] for row in res]
            has_company_id = 'company_id' in cols
            has_assigned_user_id = 'assigned_user_id' in cols
        else:
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='customers'")).fetchall()
            cols = [row[0] for row in res]
            has_company_id = 'company_id' in cols
            has_assigned_user_id = 'assigned_user_id' in cols

        # Add columns if they don't exist
        if not has_company_id:
            logger.info("Adding column: company_id")
            conn.execute(text("ALTER TABLE customers ADD COLUMN company_id INTEGER"))
            conn.commit()

        if not has_assigned_user_id:
            logger.info("Adding column: assigned_user_id")
            conn.execute(text("ALTER TABLE customers ADD COLUMN assigned_user_id INTEGER"))
            conn.commit()

    # Now backfill
    db = SessionLocal()
    try:
        # 1. Get the default company
        default_company_name = os.getenv("CMHELPER_DEFAULT_COMPANY_NAME", "Default Company")
        default_company_slug = os.getenv("CMHELPER_DEFAULT_COMPANY_SLUG", "default-company")
        company = crud.get_or_create_default_company(db, default_company_name, default_company_slug)
        logger.info(f"Default Company ID: {company.id}")

        # 2. Get the OWNER of this company
        owner_email = os.getenv("CMHELPER_OWNER_EMAIL")
        if not owner_email:
            logger.error("CMHELPER_OWNER_EMAIL environment variable is not set. Cannot backfill.")
            sys.exit(1)
            
        owner = crud.get_user_by_email(db, owner_email)
        if not owner:
            logger.error(f"Owner user '{owner_email}' not found in the database. Cannot backfill.")
            sys.exit(1)
            
        if owner.company_id != company.id:
            logger.error(f"Owner user '{owner_email}' does not belong to the default company. Cannot backfill.")
            sys.exit(1)

        logger.info(f"Default Owner User ID: {owner.id}")

        # 3. Update existing customers where company_id is NULL
        customers = db.query(models.Customer).filter(models.Customer.company_id.is_(None)).all()
        count = len(customers)
        logger.info(f"Found {count} customers with missing company_id/assigned_user_id")
        
        for customer in customers:
            customer.company_id = company.id
            customer.assigned_user_id = owner.id
            
        db.commit()
        logger.info(f"Successfully backfilled {count} customers.")

        # 4. Verify no customers have NULL company_id or assigned_user_id
        missing_count = db.query(models.Customer).filter(
            (models.Customer.company_id.is_(None)) | 
            (models.Customer.assigned_user_id.is_(None))
        ).count()
        logger.info(f"Customers with NULL ownership fields remaining: {missing_count}")
        if missing_count > 0:
            logger.warning("There are still customers with missing ownership data!")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
