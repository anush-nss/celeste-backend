import { HttpException, HttpStatus } from '@nestjs/common';

export class CustomException extends HttpException {
  constructor(
    message: string,
    status: HttpStatus,
    errors?: Record<string, any>,
  ) {
    const response = {
      message,
      errors,
    };
    super(response, status);
  }
}

// Specific custom exceptions
export class ResourceNotFoundException extends CustomException {
  constructor(resource: string, id?: string) {
    const message = id 
      ? `${resource} with ID ${id} not found` 
      : `${resource} not found`;
    super(message, HttpStatus.NOT_FOUND);
  }
}

export class ValidationException extends CustomException {
  constructor(errors: Record<string, any>) {
    super('Validation failed', HttpStatus.BAD_REQUEST, errors);
  }
}

export class UnauthorizedException extends CustomException {
  constructor(message = 'Unauthorized') {
    super(message, HttpStatus.UNAUTHORIZED);
  }
}

export class ForbiddenException extends CustomException {
  constructor(message = 'Forbidden') {
    super(message, HttpStatus.FORBIDDEN);
  }
}