import { Controller, Post, Request, UseGuards } from '@nestjs/common';
import { AuthService } from './auth.service';
import { Public } from './public.decorator';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Public()
  @Post('verify')
  async verifyToken(@Request() req) {
    const token = req.headers['authorization'];
    if (!token) {
      return { valid: false, message: 'No token provided' };
    }

    try {
      const decodedToken = await this.authService.verifyToken(token);
      return { valid: true, user: decodedToken };
    } catch (error) {
      return { valid: false, message: error.message };
    }
  }
}