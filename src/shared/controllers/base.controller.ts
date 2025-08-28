import { AppLoggerService } from '../logger/logger.service';

export class BaseController {
  constructor(protected readonly logger: AppLoggerService) {}

  protected logInfo(message: string, context?: string) {
    this.logger.log(message, context || this.constructor.name);
  }

  protected logError(message: string, trace?: string, context?: string) {
    this.logger.error(message, trace, context || this.constructor.name);
  }

  protected logWarn(message: string, context?: string) {
    this.logger.warn(message, context || this.constructor.name);
  }

  protected formatResponse<T>(data: T, message = 'Success'): T {
    // The ResponseInterceptor will format this properly
    return data;
  }

  protected formatError(error: Error, message = 'An error occurred'): never {
    // This will be caught by the HttpExceptionFilter
    throw error;
  }
}