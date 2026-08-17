import re

class SQLSafetyClassifier:
    """
    Classifies SQL statements into READ_ONLY, WRITE, or DESTRUCTIVE.
    """
    
    DESTRUCTIVE_PATTERN = re.compile(r'\b(DROP|TRUNCATE)\b', re.IGNORECASE)
    WRITE_PATTERN = re.compile(r'\b(INSERT|UPDATE|DELETE|ALTER|CREATE|GRANT|REVOKE|POLICY|COMMENT|GRANT)\b', re.IGNORECASE)
    
    READ_ONLY_PATTERN = re.compile(r'^\s*(SELECT|SHOW|EXPLAIN)\b', re.IGNORECASE)
    
    @classmethod
    def classify(cls, sql: str) -> str:
        """
        Classifies the given SQL string.
        """
        if not sql or not sql.strip():
            return "UNKNOWN"
            
        # Clean SQL: remove single-line and multi-line comments for safety check
        clean_sql = re.sub(r'--.*', '', sql)
        clean_sql = re.sub(r'/\*.*?\*/', '', clean_sql, flags=re.DOTALL)
        
        if cls.DESTRUCTIVE_PATTERN.search(clean_sql):
            return "DESTRUCTIVE"
            
        if cls.WRITE_PATTERN.search(clean_sql):
            return "WRITE"
            
        if cls.READ_ONLY_PATTERN.search(clean_sql):
            return "READ_ONLY"
            
        return "UNKNOWN"
