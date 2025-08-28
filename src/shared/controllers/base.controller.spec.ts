import { BaseController } from './base.controller';
import { AppLoggerService } from '../logger/logger.service';

class TestController extends BaseController {
  constructor(logger: AppLoggerService) {
    super(logger);
  }

  testLogInfo() {
    this.logInfo('Test info message');
  }

  testLogError() {
    this.logError('Test error message', 'Test trace');
  }

  testLogWarn() {
    this.logWarn('Test warn message');
  }

  testFormatResponse() {
    return this.formatResponse({ id: 1, name: 'Test' }, 'Success');
  }
}

describe('BaseController', () => {
  let controller: TestController;
  let logger: AppLoggerService;

  beforeEach(() => {
    logger = new AppLoggerService();
    controller = new TestController(logger);
  });

  it('should log info messages', () => {
    const logSpy = jest.spyOn(logger, 'log');
    controller.testLogInfo();
    expect(logSpy).toHaveBeenCalledWith('Test info message', 'TestController');
  });

  it('should log error messages', () => {
    const errorSpy = jest.spyOn(logger, 'error');
    controller.testLogError();
    expect(errorSpy).toHaveBeenCalledWith('Test error message', 'Test trace', 'TestController');
  });

  it('should log warn messages', () => {
    const warnSpy = jest.spyOn(logger, 'warn');
    controller.testLogWarn();
    expect(warnSpy).toHaveBeenCalledWith('Test warn message', 'TestController');
  });

  it('should format response data', () => {
    const result = controller.testFormatResponse();
    expect(result).toEqual({ id: 1, name: 'Test' });
  });
});