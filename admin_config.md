# Admin Email Configuration

## How to Add/Remove Admin Emails

To control which @somaiya.edu emails should be treated as admin accounts when signing in with Google, edit the `ADMIN_EMAILS` list in `app.py`:

```python
# Admin email configuration - Add admin emails here
ADMIN_EMAILS = [
    'admin@somaiya.edu',
    'principal@somaiya.edu', 
    'director@somaiya.edu',
    'dhruv.navadiya@somaiya.edu',  # Add specific admin emails here
    # Add more admin emails as needed
]
```

## How It Works

1. **Simple Logic**: 
   - If email is in `ADMIN_EMAILS` list → Creates admin account → Redirects to admin dashboard
   - If email is NOT in the list → Creates student account → Redirects to student dashboard

2. **Existing Users**: If the user already exists in the database:
   - The system checks both admin and student tables
   - Redirects to the appropriate dashboard based on their existing role

## Important Notes

- **Case Insensitive**: Email matching is case-insensitive
- **Domain Restriction**: Only @somaiya.edu emails are allowed
- **Default Behavior**: Any @somaiya.edu email not in the admin list becomes a student
- **Security**: Only add trusted admin emails to this list

## Example Scenarios

### Scenario 1: Admin User
- Email: `dhruv.navadiya@somaiya.edu` (in ADMIN_EMAILS list)
- Result: Creates admin account → Redirects to admin dashboard

### Scenario 2: Student User  
- Email: `student123@somaiya.edu` (not in ADMIN_EMAILS list)
- Result: Creates student account → Redirects to student dashboard

### Scenario 3: Existing User
- Email: `admin@somaiya.edu` (already exists in database)
- Result: Logs in with existing role → Redirects to appropriate dashboard

## How to Add New Admin Emails

Simply add the email to the `ADMIN_EMAILS` list in `app.py`:

```python
ADMIN_EMAILS = [
    'admin@somaiya.edu',
    'principal@somaiya.edu', 
    'director@somaiya.edu',
    'dhruv.navadiya@somaiya.edu',
    'new.admin@somaiya.edu',  # Add new admin emails here
    'another.admin@somaiya.edu',
]
```

## Troubleshooting

- If an admin email is not working, check if it's already in the student table
- If you need to change an existing user's role, you'll need to manually update the database
- Make sure the email is exactly as it appears in the ADMIN_EMAILS list 