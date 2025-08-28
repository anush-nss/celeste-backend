import { Global, Module } from '@nestjs/common';
import { FirebaseService } from './firebase.service';
import { FirestoreService } from './firestore.service';
import { AppLoggerService } from './logger/logger.service';
import { ResponseInterceptor } from './interceptors/response.interceptor';
import { HttpExceptionFilter } from './exceptions/http-exception.filter';
import { LoggingMiddleware } from './middleware/logging.middleware';

@Global()
@Module({
  providers: [
    FirebaseService,
    FirestoreService,
    AppLoggerService,
    ResponseInterceptor,
    HttpExceptionFilter,
    LoggingMiddleware,
  ],
  exports: [
    FirebaseService,
    FirestoreService,
    AppLoggerService,
    ResponseInterceptor,
    HttpExceptionFilter,
    LoggingMiddleware,
  ],
})
export class SharedModule {}