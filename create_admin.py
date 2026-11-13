"""
Standalone Admin Account Provisioning Script.

Usage:
  python create_admin.py
  python create_admin.py --username admin --email admin@company.com --password YourSecurePassword123
"""

import sys
import argparse
import getpass
from app import create_app
from app.extensions import db
from app.models.user import User


def main():
    parser = argparse.ArgumentParser(description="Create an initial System Administrator account.")
    parser.add_argument("--username", help="Admin username", default=None)
    parser.add_argument("--email", help="Admin email address", default=None)
    parser.add_argument("--password", help="Admin password (min 8 characters)", default=None)
    parser.add_argument("--show-password", action="store_true", help="Type password visibly instead of hidden")

    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        print("\n=======================================================")
        print(" Nexus CMS - Administrator Account Provisioning")
        print("=======================================================\n")

        username = args.username
        if not username:
            username = input("Enter Admin Username [admin]: ").strip() or "admin"

        email = args.email
        if not email:
            email = input("Enter Admin Email [admin@company.com]: ").strip() or "admin@company.com"

        # Check if already exists
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing:
            print(f"\n[!] A user with username '{username}' or email '{email}' already exists in PostgreSQL.")
            sys.exit(1)

        password = args.password
        if not password:
            if args.show_password:
                password = input("Enter Admin Password (min 8 characters): ").strip()
            else:
                print("\n[NOTE: Keystrokes are hidden for security. Type your password and press Enter]")
                while True:
                    password = getpass.getpass("Enter Admin Password (min 8 characters): ")
                    if len(password) < 8:
                        print("Error: Password must be at least 8 characters long.")
                        continue
                    confirm = getpass.getpass("Confirm Admin Password: ")
                    if password != confirm:
                        print("Error: Passwords do not match. Please try again.")
                        continue
                    break

        if len(password) < 8:
            print("\n[!] Error: Password must be at least 8 characters long.")
            sys.exit(1)

        # Create Admin
        admin = User(username=username, email=email, role="admin", is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        print("\n=======================================================")
        print(f" SUCCESS: Administrator account created successfully!")
        print(f" Username: {username}")
        print(f" Email:    {email}")
        print(f" Role:     Admin")
        print("=======================================================\n")
        print("You can now start the application and sign in:")
        print("  1. Run:  python run.py")
        print("  2. Open: http://127.0.0.1:5000/auth/login\n")


if __name__ == "__main__":
    main()

