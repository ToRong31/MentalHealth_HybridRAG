# Mental Health Chatbot - Docker Setup Guide

## Quick Start

### 1. Copy environment file
```bash
cp .env.example .env
```

### 2. Start PostgreSQL database
```bash
docker-compose up -d postgres
```

### 3. Verify database is running
```bash
docker-compose ps
```

You should see the `mental_health_db` container running.

### 4. Access PgAdmin (Optional)
Start PgAdmin for database management:
```bash
docker-compose up -d pgadmin
```

Then open http://localhost:5050 in your browser:
- Email: `admin@admin.com`
- Password: `admin123`

### 5. Connect to PostgreSQL using PgAdmin
1. Click "Add New Server"
2. General tab:
   - Name: Mental Health DB
3. Connection tab:
   - Host: `postgres` (when using Docker) or `localhost` (from host machine)
   - Port: `5432`
   - Database: `mental_health_db`
   - Username: `postgres`
   - Password: `postgres123`

### 6. Install backend dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 7. Run the backend
```bash
cd backend
python main.py
```

The API will be available at http://localhost:8000

### 8. Run the frontend
```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173

## Database Schema

The database is automatically initialized with the following tables:
- `users` - User accounts
- `conversations` - Chat conversations
- `messages` - Chat messages

A demo user is created:
- Email: `demo@example.com`
- Password: `demo123`

## Useful Docker Commands

### View logs
```bash
# All services
docker-compose logs -f

# PostgreSQL only
docker-compose logs -f postgres
```

### Stop services
```bash
docker-compose down
```

### Stop and remove all data
```bash
docker-compose down -v
```

### Restart services
```bash
docker-compose restart
```

### Access PostgreSQL CLI
```bash
docker-compose exec postgres psql -U postgres -d mental_health_db
```

### Backup database
```bash
docker-compose exec postgres pg_dump -U postgres mental_health_db > backup.sql
```

### Restore database
```bash
docker-compose exec -T postgres psql -U postgres mental_health_db < backup.sql
```

## Environment Variables

Edit `.env` file to customize:

- **Database**: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- **JWT**: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_DAYS`
- **API**: `API_HOST`, `API_PORT`
- **PgAdmin**: `PGADMIN_EMAIL`, `PGADMIN_PASSWORD`, `PGADMIN_PORT`

## Troubleshooting

### Port already in use
If port 5432 is already in use, change `DB_PORT` in `.env`:
```
DB_PORT=5433
```
Then update docker-compose.yml port mapping to `"5433:5432"`.

### Connection refused
Make sure the database is running:
```bash
docker-compose ps
```

Check the logs:
```bash
docker-compose logs postgres
```

### Reset database
To start fresh:
```bash
docker-compose down -v
docker-compose up -d postgres
```

This will delete all data and recreate the database from scratch.
