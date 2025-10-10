# Flask Chat Application

A real-time chat application with email verification and file uploads.

## Features

- Email verification system
- Real-time chat messaging
- File uploads (images, audio, documents)
- User authentication
- Responsive design

## Local Development

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables (optional for email):
   ```bash
   export SECRET_KEY=your-secret-key
   export DATABASE_URL=sqlite:///chat.db
   export EMAIL_USER=your-email@gmail.com
   export EMAIL_PASSWORD=your-app-password