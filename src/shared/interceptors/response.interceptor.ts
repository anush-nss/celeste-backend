import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { AppLoggerService } from '../logger/logger.service';

export interface Response<T> {
  statusCode: number;
  message: string;
  data: T;
  timestamp: string;
  path: string;
}

@Injectable()
export class ResponseInterceptor<T> implements NestInterceptor<T, Response<T>> {
  constructor(private readonly logger: AppLoggerService) {}

  intercept(
    context: ExecutionContext,
    next: CallHandler,
  ): Observable<Response<T>> {
    const ctx = context.switchToHttp();
    const request = ctx.getRequest();
    const response = ctx.getResponse();
    
    // Log the incoming request
    this.logger.log(
      `Incoming Request: ${request.method} ${request.url}`,
      `${ResponseInterceptor.name} - ${request.ip}`,
    );

    return next.handle().pipe(
      map((data) => {
        const statusCode = response.statusCode || 200;
        const result = {
          statusCode,
          message: this.getMessageForStatusCode(statusCode),
          data: data || null,
          timestamp: new Date().toISOString(),
          path: request.url,
        };
        
        // Log the outgoing response
        this.logger.log(
          `Outgoing Response: ${statusCode} - ${request.method} ${request.url}`,
          `${ResponseInterceptor.name}`,
        );
        
        return result;
      }),
    );
  }

  private getMessageForStatusCode(statusCode: number): string {
    switch (statusCode) {
      case 200:
        return 'Success';
      case 201:
        return 'Created';
      case 204:
        return 'No Content';
      case 400:
        return 'Bad Request';
      case 401:
        return 'Unauthorized';
      case 403:
        return 'Forbidden';
      case 404:
        return 'Not Found';
      case 500:
        return 'Internal Server Error';
      default:
        return 'Success';
    }
  }
}