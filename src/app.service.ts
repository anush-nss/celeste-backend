import { Injectable } from '@nestjs/common';
import { AppLoggerService } from './shared/logger/logger.service';

@Injectable()
export class AppService {
  constructor(private readonly logger: AppLoggerService) {}

  getHello(): string {
    this.logger.log('Hello endpoint accessed', AppService.name);
    return 'Hello World!';
  }
}
