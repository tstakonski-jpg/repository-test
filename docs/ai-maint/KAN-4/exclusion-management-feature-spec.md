# KAN-4: Exclusion Management Refactor

## 1. Introduction
This document outlines the requirements and proposed design for refactoring the exclusion management system. The goal is to enhance flexibility, improve UI management, and enable selective bypassing of exclusion rules, particularly for priority projects.

## 2. Desired Outcomes
*   **Selective Bypass**: Enable the ability to bypass exclusions specifically for priority projects, while maintaining exclusion logic for other worklist types.
*   **Improved UI Management**: Provide a more intuitive and centralized user interface for managing exclusion rules.
*   **Hierarchy and Totals**: Maintain the existing functionality of showing hierarchy with total amounts in AR and within each worklist type, accurately reflecting applied or bypassed exclusions.

## 3. General Idea
The core concept involves shifting exclusion rules from being tightly coupled with individual worklists to becoming system-level rules. These system rules will be categorized and can be selectively bypassed during worklist creation.

*   **Exclusion Grouping**: Exclusion rules will be categorized into "Temporary Holds" and "Permanent Holds".
*   **Bypass Option**: When creating a worklist, users will have an option to bypass either temporary, permanent, or both types of exclusions. This is primarily intended for scenarios where a subset of items needs to be worked regardless of recent activity or other standard exclusion criteria.
*   **System Rules**: Exclusions will be managed as system-wide rules rather than worklist-specific configurations. While the underlying logic might still interact with "worklists" conceptually, the management UI will be distinct and centralized.

## 4. Proposed Solution Details

### 4.1. Data Model Changes
*   **SystemExclusionRule Entity**:
    *   `id` (PK)
    *   `name` (e.g., "Recently Worked", "Recently Billed")
    *   `description`
    *   `type` (ENUM: 'TEMPORARY', 'PERMANENT')
    *   `criteria` (JSONB or similar, defining the actual exclusion logic, e.g., `{"field": "last_worked_date", "operator": "within", "value": "30 days"}`)
    *   `isActive` (BOOLEAN)
    *   `createdAt`, `updatedAt`

### 4.2. API Endpoints
*   **GET /api/system-exclusion-rules**: Retrieve all system exclusion rules.
*   **POST /api/system-exclusion-rules**: Create a new system exclusion rule.
*   **PUT /api/system-exclusion-rules/{id}**: Update an existing system exclusion rule.
*   **DELETE /api/system-exclusion-rules/{id}**: Delete a system exclusion rule.
*   **POST /api/worklists**: Modify this endpoint to accept new parameters:
    *   `bypassTemporaryExclusions` (BOOLEAN, default: false)
    *   `bypassPermanentExclusions` (BOOLEAN, default: false)

### 4.3. Backend Logic
*   **Worklist Generation Service**:
    1.  When a request to create a worklist is received, retrieve all active `SystemExclusionRule`s.
    2.  Based on the `bypassTemporaryExclusions` and `bypassPermanentExclusions` flags in the request:
        *   If `bypassTemporaryExclusions` is true, filter out all rules where `type` is 'TEMPORARY'.
        *   If `bypassPermanentExclusions` is true, filter out all rules where `type` is 'PERMANENT'.
    3.  Apply the remaining (non-bypassed) exclusion rules to the set of potential items for the worklist.
    4.  Generate the worklist with the filtered items, ensuring correct hierarchy and AR totals are calculated.

### 4.4. User Interface (UI)
*   **Exclusion Rules Management Page**:
    *   A new dedicated page accessible from the main navigation (e.g., "Settings" -> "Exclusion Rules").
    *   Display a table of all system exclusion rules, showing name, type, criteria summary, and active status.
    *   Buttons for "Add New Rule", "Edit", "Delete", "Activate/Deactivate".
    *   Clear visual distinction between temporary and permanent rules.
*   **Create Worklist Form**:
    *   Add two new checkboxes or a dropdown/radio button group:
        *   "[ ] Bypass Temporary Exclusions"
        *   "[ ] Bypass Permanent Exclusions"
    *   Include tooltips or contextual help text explaining the impact of these options.

## 5. Out of Scope
*   Creation of standard exclusions (e.g., "recently worked", "recently billed") at go-live. This can be a follow-up task once the core system is in place.
*   Complex rule chaining or priority between exclusion rules (beyond temporary/permanent grouping).

## 6. Open Questions / Considerations
*   What specific criteria will define "priority projects" that allow exclusion bypass? Is it a worklist tag, a user permission, or something else?
*   How will existing worklist-specific exclusions be handled during migration to the new system-level rules?
*   Detailed specification of the `criteria` JSONB structure for various exclusion types.
