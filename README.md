<p align="center">
  <a href="http://nestjs.com/" target="blank"><img src="https://nestjs.com/img/logo-small.svg" width="120" alt="Nest Logo" /></a>
</p>

[circleci-image]: https://img.shields.io/circleci/build/github/nestjs/nest/master?token=abc123def456
[circleci-url]: https://circleci.com/gh/nestjs/nest

  <p align="center">A progressive <a href="http://nodejs.org" target="_blank">Node.js</a> framework for building efficient and scalable server-side applications.</p>
    <p align="center">
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/v/@nestjs/core.svg" alt="NPM Version" /></a>
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/l/@nestjs/core.svg" alt="Package License" /></a>
<a href="https://www.npmjs.com/~nestjscore" target="_blank"><img src="https://img.shields.io/npm/dm/@nestjs/common.svg" alt="NPM Downloads" /></a>
<a href="https://circleci.com/gh/nestjs/nest" target="_blank"><img src="https://img.shields.io/circleci/build/github/nestjs/nest/master" alt="CircleCI" /></a>
<a href="https://discord.gg/G7Qnnhy" target="_blank"><img src="https://img.shields.io/badge/discord-online-brightgreen.svg" alt="Discord" /></a>
<a href="https://opencollective.com/nest#backer" target="_blank"><img src="https://opencollective.com/nest/backers/badge.svg" alt="Backers on Open Collective" /></a>
<a href="https://opencollective.com/nest#sponsor" target="_blank"><img src="https://opencollective.com/nest/sponsors/badge.svg" alt="Sponsors on Open Collective" /></a>
  <a href="https://paypal.me/kamilmysliwiec" target="_blank"><img src="https://img.shields.io/badge/Donate-PayPal-ff3f59.svg" alt="Donate us" /></a>
    <a href="https://opencollective.com/nest#sponsor"  target="_blank"><img src="https://img.shields.io/badge/Support%20us-Open%20Collective-41B883.svg" alt="Support us"></a>
  <a href="https://twitter.com/nestframework" target="_blank"><img src="https://img.shields.io/twitter/follow/nestframework.svg?style=social&label=Follow" alt="Follow us on Twitter"></a>
</p>
  <!--[![Backers on Open Collective](https://opencollective.com/nest/backers/badge.svg)](https://opencollective.com/nest#backer)
  [![Sponsors on Open Collective](https://opencollective.com/nest/sponsors/badge.svg)](https://opencollective.com/nest#sponsor)-->

## Description

Celeste E-Commerce API - A robust, scalable, and feature-rich e-commerce backend built with NestJS, TypeScript, and Firebase. This API provides a comprehensive set of endpoints to power a modern online store, from user management and product catalogs to order processing and inventory tracking.

## Key Features

- **Modular Architecture**: Organized into distinct modules for each domain (e.g., `users`, `products`, `orders`), promoting separation of concerns and scalability.
- **Firebase Integration**: Leverages Firebase for authentication (Firebase Auth) and database (Firestore), providing a reliable and scalable backend infrastructure.
- **Centralized Error Handling**: A global exception filter ensures consistent and informative error responses across the API.
- **Standardized Responses**: A global response interceptor formats all successful responses, providing a uniform structure for clients.
- **Comprehensive Logging**: Middleware and a dedicated logger service provide detailed request/response logging with contextual information for effective monitoring and debugging.
- **Zod Validation**: All incoming request data is validated using Zod schemas, ensuring type safety and data integrity.
- **Authentication & Authorization**: Secure endpoints using JWT-based authentication with Firebase Auth. Public and protected routes are clearly defined.
- **Configuration Management**: Environment-based configuration for easy management of settings across different environments (development, production, etc.).

## Project Structure

The project follows a standard NestJS project structure, with the core logic located in the `src` directory.

```
src/
├── auth/             # Authentication (Firebase Auth)
├── categories/       # Product categories
├── config/           # Environment configuration
├── discounts/        # Discount management
├── inventory/        # Inventory tracking
├── orders/           # Order management
├── products/         # Product and featured product management
├── promotions/       # Promotional campaigns
├── shared/           # Shared modules, services, and utilities
│   ├── controllers/  # Base controller logic
│   ├── exceptions/   # Custom exceptions and filter
│   ├── interceptors/ # Response formatting interceptor
│   ├── logger/       # Application logger service
│   ├── middleware/   # Request logging middleware
│   └── pipes/        # Zod validation pipe
├── stores/           # Physical store information
└── users/            # User management
```

## Project Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd celeste
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

## Firebase Setup

1.  Create a Firebase project at [https://console.firebase.google.com/](https://console.firebase.google.com/).
2.  Enable **Authentication** (e.g., Email/Password).
3.  Set up **Firestore** as your database.
4.  Generate a service account key:
    -   Go to **Project Settings** > **Service Accounts**.
    -   Click **"Generate new private key"**.
    -   Save the downloaded JSON file in a secure location.

## Environment Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```

2.  Update the `.env` file with your Firebase project details and other configurations:
    -   `GOOGLE_APPLICATION_CREDENTIALS`: The absolute path to your downloaded Firebase service account JSON file.
    -   `FIREBASE_PROJECT_ID`: Your Firebase project ID.
    -   `FIREBASE_PRIVATE_KEY`: The private key from the service account file.
    -   `FIREBASE_CLIENT_EMAIL`: The client email from the service account file.
    -   `PORT`: The port on which the application will run (e.g., 3000).
    -   `NODE_ENV`: The application environment (e.g., `development`).

## Available Scripts

-   **Run in development mode:**
    ```bash
    $ npm run start:dev
    ```

-   **Build for production:**
    ```bash
    $ npm run build
    ```

-   **Run in production mode:**
    ```bash
    $ npm run start:prod
    ```

-   **Run tests:**
    ```bash
    # unit tests
    $ npm run test

    # e2e tests
    $ npm run test:e2e

    # test coverage
    $ npm run test:cov
    ```

-   **Lint and format:**
    ```bash
    # lint
    $ npm run lint

    # format
    $ npm run format
    ```

## API Documentation

Detailed API documentation, including endpoint specifications, data models, and authentication requirements, can be found in the [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) file.

## License

This project is [MIT licensed](https://github.com/nestjs/nest/blob/master/LICENSE).