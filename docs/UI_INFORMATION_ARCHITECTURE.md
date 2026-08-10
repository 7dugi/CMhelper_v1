# UI Information Architecture

This document defines the navigational direction and layout for CMhelper's future frontend architecture.

## Design Principles

- **Visual Reference**: The Visily CRM template is used as a visual reference (for layout, components, and structure), but it must NOT be blindly copied. 
- **Identity**: Retain CMhelper's existing brand identity, including the Dark Theme.
- **Role-Based Views**: The UI will adapt based on the user's role (OWNER vs. USER). Features and menus unavailable to a USER must be hidden entirely, not just disabled.
- **Entity Separation**: Future iterations will adapt the UI to handle the Customer-Contract 1:N separation.

## Proposed Navigation Structure

The main side navigation (Sidebar) will be organized as follows:

### 1. Dashboard
- **Purpose**: A high-level overview of the workspace.
- **Content**: 
  - Company-wide or user-scoped statistics (total customers, active contracts, etc.)
  - Upcoming expirations (e.g., expiry in 1 month, 3 months)
  - Recent consultations or alerts
  - Revenue or sales summaries (if applicable)

### 2. Customers
- **Purpose**: The foundational registry of all customers.
- **Content**:
  - A table displaying basic customer info (Name, Contact, Region, Company)
  - Number of active contracts per customer
  - Assigned user (visible only to OWNERs)
  - A detailed view for each customer (accessible via click), which will include tabs for "Info", "Contracts", and "History".

### 3. Contracts
- **Purpose**: A dedicated view for managing financial/vehicle contracts across all customers.
- **Content**:
  - A table of all contracts (Vehicle Model, Capital, Expiry Date, Status)
  - Filters to quickly find contracts expiring soon or terminated contracts
  - Useful for bulk actions (e.g., sending renewal notices)

### 4. Consultations / Pipeline
- **Purpose**: Managing sales opportunities and leads.
- **Content**:
  - A Kanban board or structured list representing the sales pipeline
  - Tracking prospects from initial inquiry to signed contract
  - Replaces the simple `is_prospect` boolean with structured stages (e.g., "Inquiry", "Quote Sent", "Under Review", "Closed Won", "Closed Lost")

### 5. Messaging / Marketing
- **Purpose**: Managing communications with customers.
- **Content**:
  - Message task queue (KakaoTalk / SMS)
  - Template management
  - Bulk sending interface
  - Marketing automation configuration

### 6. Inventory
- **Purpose**: Managing or viewing vehicle stock.
- **Content**:
  - Available vehicles for matching with customer inquiries
  - Fast-track assignments

### 7. Users (OWNER Only)
- **Purpose**: Managing organizational access.
- **Content**:
  - Active users, pending approvals, and deactivated users
  - Assigning roles
  - Managing invite codes

### 8. Settings
- **Purpose**: System and account configuration.
- **Content**:
  - Profile settings (Email, Password)
  - Theme preferences
  - Company-wide settings (OWNER only)
  - Custom field definitions (OWNER only)

## Phased Rollout

- **Phase 1 (Current)**: Minor adjustments (e.g., displaying the assignee column on the existing Customer list).
- **Phase 2**: Implement routing (e.g., React Router) to physically separate the "Customers", "Users", and "Settings" views from a single-page list.
- **Phase 3**: Introduce the "Contracts" and "Consultations/Pipeline" views alongside the database refactoring.
