# API Documentation
## AI-Powered Elderly Healthcare and Medication Assistance System

**Base URL:** `http://localhost:5000/api`  
**Authentication:** JWT Bearer Token (include in `Authorization: Bearer <token>` header)

---

## Authentication

### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "username": "dr_radhika",
  "email": "radhika@healthcare.com",
  "password": "Test@1234",
  "role": "caretaker",
  "full_name": "Dr. Radhika Sharma",
  "phone": "+919876543210"
}
```

**Response (201):**
```json
{
  "message": "Registration successful",
  "user": { "id": 1, "username": "dr_radhika", "role": "caretaker" },
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc..."
}
```

---

### POST /auth/login
Login to get JWT tokens.

**Request Body:**
```json
{ "username": "dr_radhika", "password": "Test@1234" }
```

**Response (200):**
```json
{
  "message": "Login successful",
  "user": { "id": 1, "username": "dr_radhika" },
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc..."
}
```

---

### GET /auth/me
Get current user profile. **Requires Auth.**

**Response (200):**
```json
{ "user": { "id": 1, "username": "dr_radhika", "role": "caretaker", "email": "..." } }
```

---

### POST /auth/logout
Logout (client should discard tokens). **Requires Auth.**

---

### PUT /auth/change-password
Change user password. **Requires Auth.**

**Request Body:**
```json
{ "current_password": "OldPass@1", "new_password": "NewPass@2" }
```

---

## Elders

### GET /elders
Get all elders (filtered by current user's assignments). **Requires Auth.**

**Query Params:** `page`, `per_page`, `search`

**Response (200):**
```json
{
  "elders": [{ "id": 1, "name": "Ramu Naidu", "age": 75, "gender": "male", ... }],
  "total": 5, "pages": 1, "current_page": 1
}
```

---

### POST /elders
Create a new elder profile. **Requires Auth.**

**Request Body:**
```json
{
  "name": "Ramu Naidu",
  "age": 75,
  "gender": "male",
  "blood_group": "O+",
  "medical_conditions": "Type 2 Diabetes, Hypertension",
  "allergies": "Penicillin",
  "emergency_contact": "+919876501001",
  "emergency_contact_name": "Suresh Naidu",
  "address": "Jubilee Hills, Hyderabad",
  "notes": "Prefers Telugu communication"
}
```

---

### GET /elders/:id
Get elder by ID. **Requires Auth.**

---

### PUT /elders/:id
Update elder profile. **Requires Auth.**

---

### DELETE /elders/:id
Soft delete elder (deactivates). **Requires Auth.**

---

### GET /elders/:id/summary
Get elder with statistics. **Requires Auth.**

---

## Medicines

### GET /medicines
Get all medicines. **Requires Auth.**

**Query Params:** `page`, `per_page`, `is_active`

---

### POST /medicines
Add a new medicine prescription. **Requires Auth.**

**Request Body:**
```json
{
  "elder_id": 1,
  "name": "Metformin",
  "generic_name": "Metformin HCL",
  "dosage": "500mg",
  "frequency": "Twice daily",
  "route": "oral",
  "prescribed_by": "Dr. Srinivas",
  "start_date": "2024-01-01",
  "instructions": "Take with food",
  "purpose": "Type 2 Diabetes management"
}
```

---

### GET /medicines/elder/:elder_id
Get all medicines for a specific elder. **Requires Auth.**

---

### GET /medicines/:id
Get medicine by ID. **Requires Auth.**

---

### PUT /medicines/:id
Update medicine. **Requires Auth.**

---

### DELETE /medicines/:id
Deactivate medicine. **Requires Auth.**

---

## Schedules

### GET /schedules
Get all schedules. **Requires Auth.**

**Query Params:** `elder_id`

---

### POST /schedules
Create a medication schedule. **Requires Auth.**

**Request Body:**
```json
{
  "medicine_id": 1,
  "elder_id": 1,
  "scheduled_time": "08:00",
  "day_of_week": "all",
  "recurrence": "daily",
  "meal_timing": "with_meal",
  "notes": "Take with breakfast"
}
```

---

### GET /schedules/today/:elder_id
Get today's schedule with adherence status. **Requires Auth.**

**Response:**
```json
{
  "schedules": [{
    "id": 1,
    "medicine_name": "Metformin",
    "scheduled_time": "08:00:00",
    "adherence_status": "taken",
    "adherence_id": 5
  }],
  "date": "2024-01-15"
}
```

---

### PUT /schedules/:id
Update schedule. **Requires Auth.**

---

### DELETE /schedules/:id
Delete schedule. **Requires Auth.**

---

## Adherence

### POST /adherence/mark
Mark a dose as taken, missed, or skipped. **Requires Auth.**

**Request Body:**
```json
{
  "schedule_id": 1,
  "elder_id": 1,
  "medicine_id": 1,
  "scheduled_datetime": "2024-01-15T08:00:00",
  "status": "taken",
  "notes": "Taken with breakfast"
}
```

**Status values:** `taken` | `missed` | `skipped`

---

### GET /adherence/stats/:elder_id
Get 30-day adherence statistics. **Requires Auth.**

**Response:**
```json
{
  "elder_id": 1,
  "period_days": 30,
  "total": 60,
  "taken": 52,
  "missed": 6,
  "skipped": 2,
  "adherence_rate": 86.7,
  "daily_breakdown": [{ "date": "2024-01-15", "day": "Mon", "taken": 4, "total": 4, "rate": 100.0 }]
}
```

---

### GET /adherence/history/:elder_id
Get paginated adherence history. **Requires Auth.**

---

## Alerts

### GET /alerts/unread
Get unread alerts (max 10). **Requires Auth.**

**Response:**
```json
{
  "count": 3,
  "alerts": [{ "id": 1, "alert_type": "missed_dose", "message": "...", "severity": "high" }]
}
```

---

### PUT /alerts/:id/read
Mark alert as read. **Requires Auth.**

---

### PUT /alerts/mark-all-read
Mark all alerts as read. **Requires Auth.**

---

## Dashboard

### GET /dashboard/stats
Get aggregate statistics. **Requires Auth.**

**Response:**
```json
{
  "total_elders": 5,
  "total_active_medicines": 12,
  "today_schedules": 8,
  "today_taken": 6,
  "today_adherence_rate": 75.0,
  "unread_alerts": 2,
  "monthly_adherence_rate": 87.5
}
```

---

### GET /dashboard/adherence-chart
Get weekly/daily adherence data for charts. **Requires Auth.**

**Query Params:** `days` (default: 7), `elder_id`

---

### GET /dashboard/today-schedule
Get today's full schedule across all elders. **Requires Auth.**

---

## Chatbot

### POST /chatbot/message
Send a message to the AI health assistant. **Requires Auth.**

**Request Body:**
```json
{
  "message": "What are the side effects of Metformin?",
  "elder_id": 1,
  "language": "en"
}
```

**Language values:** `en` (English) | `te` (Telugu) | `hi` (Hindi)

**Response:**
```json
{
  "response": "Metformin's common side effects include nausea...",
  "source": "rule_based",
  "suggestions": ["What to avoid with Metformin?", "..."],
  "language": "en"
}
```

---

### GET /chatbot/history
Get conversation history. **Requires Auth.**

---

### DELETE /chatbot/clear
Clear conversation history. **Requires Auth.**

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Bad Request - Invalid input data |
| 401 | Unauthorized - Token missing/invalid/expired |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Duplicate resource (e.g., username taken) |
| 500 | Internal Server Error |

**Error Response Format:**
```json
{ "error": "Description of the error" }
```
