# Pegasus Frontend

A React + Vite application for data validation and mismatch reporting. The frontend provides a user interface for running validations and viewing detailed mismatch reports.

## Prerequisites

- **Node.js**: v18.0.0 or higher
- **npm**: v9.0.0 or higher

Verify your installation:
```bash
node --version
npm --version
```

## Installation

1. Navigate to the frontend directory:
```bash
cd pegasus-frontend
```

2. Install dependencies:
```bash
npm install
```

## Running the Project

### Development Mode

Start the development server with hot module replacement (HMR):

```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Production Build

Create an optimized production build:

```bash
npm run build
```

Built files will be output to the `dist/` directory.

### Preview Production Build

Preview the production build locally:

```bash
npm run preview
```

The preview will be served at `http://localhost:4173`

### Linting

Check code quality with ESLint:

```bash
npm run lint
```

## Project Structure

```
pegasus-frontend/
├── src/
│   ├── components/         # Reusable React components
│   │   ├── ValidationPanel.jsx
│   │   └── MismatchSampleRows.jsx
│   ├── App.jsx            # Main application component
│   ├── main.jsx           # Application entry point
│   ├── App.css            # Application styles
│   └── index.css          # Global styles
├── public/                # Static assets
├── package.json          # Project dependencies and scripts
├── vite.config.js        # Vite configuration
└── eslint.config.js      # ESLint configuration
```

## Available Components

- **ValidationPanel**: Main component for running validations
- **MismatchSampleRows**: Displays detailed mismatch records

## Connecting to Backend

The frontend communicates with the backend API at `http://localhost:8000`. Ensure the backend is running before starting the frontend development server.

## Tech Stack

- **React**: ^19.2.5
- **Vite**: ^8.0.10
- **ESLint**: ^10.2.1

## Development Tips

- Hot Module Replacement (HMR) is enabled by default during development
- ESLint rules are configured to catch common React issues
- Use browser DevTools to debug React component state and props

## Contributing

1. Keep components modular and reusable
2. Follow ESLint rules
3. Test thoroughly before committing
4. Update this README when adding new features
