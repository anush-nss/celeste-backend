import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { AppLoggerService } from '../logger/logger.service';

@Injectable()
export class LoggingMiddleware implements NestMiddleware {
  constructor(private readonly logger: AppLoggerService) {}

  use(req: Request, res: Response, next: NextFunction) {
    const { method, originalUrl, ip } = req;
    const startTime = Date.now();

    // Log incoming request
    this.logger.log(
      `Incoming Request: ${method} ${originalUrl}`,
      `${LoggingMiddleware.name} - ${ip}`,
    );

    // Capture the response finish event to log response details
    res.on('finish', () => {
      const { statusCode } = res;
      const duration = Date.now() - startTime;
      
      this.logger.log(
        `Outgoing Response: ${statusCode} - ${method} ${originalUrl} - ${duration}ms`,
        `${LoggingMiddleware.name}`,
      );
    });

    next();
  }
}