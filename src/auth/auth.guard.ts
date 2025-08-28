import {
  Injectable,
  CanActivate,
  ExecutionContext,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthService } from './auth.service';

@Injectable()
export class AuthGuard implements CanActivate {
  constructor(private readonly authService: AuthService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const authHeader = request.headers['authorization'];

    if (!authHeader) {
      throw new UnauthorizedException('Authorization header is required');
    }

    try {
      const decodedToken = await this.authService.verifyToken(authHeader);
      
      if (!decodedToken.role) {
        throw new UnauthorizedException('User role not found in token');
      }

      // Attach user info and role to request for use in controllers
      request.user = { ...decodedToken, role: decodedToken.role };
      return true;
    } catch (error) {
      throw new UnauthorizedException('Invalid authentication token');
    }
  }
}
