import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { AuthGuard } from './auth.guard';
import { IS_PUBLIC_KEY } from './public.decorator';
import { AuthService } from './auth.service';
import { ConfigService } from '@nestjs/config';
import { USER_ROLES } from '../shared/constants';

@Injectable()
export class JwtAuthGuard extends AuthGuard implements CanActivate {
  constructor(
    private reflector: Reflector,
    authService: AuthService,
    private configService: ConfigService,
  ) {
    super(authService);
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) {
      return true;
    }

    const request = context.switchToHttp().getRequest();

    // Development mode bypass for test user
    if (this.configService.get('NODE_ENV') === 'development') {
      const testUserId = request.headers['x-test-user-id'];
      if (testUserId) {
        request.user = {
          uid: testUserId,
          role: USER_ROLES.CUSTOMER, // Default role for test user
        };
        return true;
      }
    }

    return super.canActivate(context);
  }
}