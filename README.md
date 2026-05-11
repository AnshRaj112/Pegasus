# Pegasus

Pegasus is a comprehensive data validation platform that compares CSV files and generates detailed mismatch reports. It consists of a React-based frontend for user interaction and a FastAPI-based backend for validation processing.

## Project Structure

```
Pegasus/
├── pegasus-backend/        # FastAPI backend service
├── pegasus-frontend/       # React + Vite frontend application
├── pegasus-infra/          # Infrastructure and deployment configs
├── benchmarks/             # Performance benchmarks
├── docs/                   # Project documentation
├── test-data/              # Sample test data files
└── scripts/                # Utility scripts
```

## Quick Start

### Prerequisites

- **Node.js**: v18.0.0 or higher
- **Python**: 3.12 or higher
- **npm**: v9.0.0 or higher
- **PostgreSQL** or **SQLite**: For database (SQLite for development)

### Backend Setup

1. Navigate to the backend directory:
```bash
cd pegasus-backend
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with database configuration:
```bash
DATABASE_URL=sqlite:///./pegasus.db
```

5. Run database migrations:
```bash
alembic upgrade head
```

6. Start the backend server:
```bash
uvicorn pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API will be available at: `http://localhost:8000`
- **Swagger Documentation**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc

### Frontend Setup

1. Navigate to the frontend directory (in a new terminal):
```bash
cd pegasus-frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

Frontend will be available at: `http://localhost:5173`

## Running Tests

### Backend Tests

```bash
cd pegasus-backend
pytest tests/
```

Run with coverage:
```bash
pytest --cov=pegasus tests/
```

### Frontend Tests (if configured)

```bash
cd pegasus-frontend
npm test
```

## Building for Production

### Backend

```bash
cd pegasus-backend
# Run with production settings
uvicorn pegasus.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

```bash
cd pegasus-frontend
npm run build
```

Built files will be in `dist/` directory.

## Key Features

### Backend
- ✅ FastAPI REST API for validation operations
- ✅ PostgreSQL/SQLite database support
- ✅ CSV file comparison and validation
- ✅ SHA256-based composite UID generation
- ✅ Detailed mismatch reporting with row-level details
- ✅ Database migrations with Alembic
- ✅ Asynchronous operations for performance
- ✅ Health check endpoints
- ✅ Comprehensive error handling

### Frontend
- ✅ React + Vite modern tech stack
- ✅ Responsive validation panel interface
- ✅ Detailed mismatch record viewing
- ✅ Real-time API communication
- ✅ ESLint code quality checks
- ✅ Hot Module Replacement during development

## API Documentation

### Health Check
```
GET /health
```

### Validation Endpoints
```
GET    /api/v1/validation/runs              # List all validation runs
POST   /api/v1/validation/runs              # Create and run new validation
GET    /api/v1/validation/runs/{run_id}     # Get validation run details
GET    /api/v1/validation/runs/{run_id}/mismatches  # Get mismatch records
```

Refer to the [Backend README](./pegasus-backend/README.md) for detailed API documentation.

## Development Workflow

### Making Changes

1. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make changes and test thoroughly

3. Commit with descriptive messages:
```bash
git add .
git commit -m "Add feature description"
```

4. Push and create a pull request:
```bash
git push origin feature/your-feature-name
```

### Code Quality

- Backend: Follow PEP 8 style guide, write tests, use type hints
- Frontend: Use ESLint rules, keep components modular, test before committing

## Troubleshooting

### Backend Issues
- **Database connection error**: Check `DATABASE_URL` in `.env`
- **Port 8000 already in use**: Change port with `--port 9000`
- **Module import errors**: Activate virtual environment and reinstall dependencies

### Frontend Issues
- **Port 5173 already in use**: Vite will use next available port
- **npm dependencies error**: Delete `node_modules` and `package-lock.json`, then reinstall

### Combined Issues
- Ensure backend is running before starting frontend
- Check CORS settings if API calls fail
- Clear browser cache if frontend doesn't update

## Environment Configuration

### Backend `.env` file

```bash
# Database
DATABASE_URL=sqlite:///./pegasus.db

# API
API_TITLE=Pegasus API
API_VERSION=1.0.0
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=["http://localhost:5173"]
```

### Frontend Vite Configuration

- Default port: `5173`
- Backend proxy: Configured to forward to `localhost:8000`
- Check `vite.config.js` for details

## Docker Support

### Build Backend Docker Image

```bash
cd pegasus-backend
docker build -t pegasus-backend .
```

### Run Backend Container

```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=sqlite:///./pegasus.db \
  pegasus-backend
```

## Additional Resources

- [Backend README](./pegasus-backend/README.md) - Detailed backend documentation
- [Frontend README](./pegasus-frontend/README.md) - Detailed frontend documentation
- [Test Data](./test-data/) - Sample CSV files for testing

## Tech Stack

### Backend
- FastAPI ^0.115.0
- SQLAlchemy ^2.0.36
- Polars ^1.0.0
- Alembic ^1.14.0
- Pydantic ^2.10.0

### Frontend
- React ^19.2.5
- Vite ^8.0.10
- ESLint ^10.2.1

## Contributing

1. Follow the code style guidelines
2. Write tests for new features
3. Keep documentation updated
4. Use meaningful commit messages

## License

Proprietary - Pegasus Project

## Support

For issues, questions, or suggestions, please contact the development team.
