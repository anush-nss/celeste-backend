import {
  Controller,
  Post,
  Request as NestRequest,
  UseGuards,
  Get,
  Param,
  Res as NestRes,
  HttpStatus,
  Body,
  UsePipes,
  UnauthorizedException,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { AuthService } from './auth.service';
import { Public } from './public.decorator';
import { ConfigService } from '@nestjs/config';
import * as https from 'https';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import { LoginSchema, RegisterSchema } from './schemas/auth.schema';
import { FirestoreService } from '../shared/firestore.service';
import { User } from '../users/schemas/user.schema';

@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly configService: ConfigService,
    private readonly firestoreService: FirestoreService,
  ) {}

  @Public()
  @Post('verify')
  async verifyToken(@NestRequest() req: Request) {
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

  @Public()
  @Get('test-token/:uid')
  async getTestToken(@Param('uid') uid: string, @NestRes() res: Response) {
    if (this.configService.get('NODE_ENV') !== 'development') {
      return res.status(HttpStatus.FORBIDDEN).json({
        message: 'This endpoint is only available in development mode',
      });
    }

    try {
      // Set custom claim for the test user
      await this.authService.setCustomUserClaims(uid, {
        role: USER_ROLES.CUSTOMER,
      });
      const customToken = await this.authService.generateCustomToken(uid);
      const apiKey = this.configService.get('firebase.apiKey');
      const options = {
        hostname: 'identitytoolkit.googleapis.com',
        path: `/v1/accounts:signInWithCustomToken?key=${apiKey}`,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      };

      const req = https.request(options, (apiRes) => {
        let data = '';
        apiRes.on('data', (chunk) => {
          data += chunk;
        });
        apiRes.on('end', () => {
          res.status(apiRes.statusCode).json(JSON.parse(data));
        });
      });

      req.on('error', (error) => {
        res.status(HttpStatus.INTERNAL_SERVER_ERROR).json({
          message: 'Failed to exchange custom token',
          error: error.message,
        });
      });

      req.write(
        JSON.stringify({ token: customToken, returnSecureToken: true }),
      );
      req.end();
    } catch (error) {
      res
        .status(HttpStatus.INTERNAL_SERVER_ERROR)
        .json({ message: error.message });
    }
  }

  @Public()
  @Post('log-in')
  @UsePipes(new ZodValidationPipe(LoginSchema))
  async login(@Body() body: { token: string }) {
    try {
      const decodedToken = await this.authService.verifyToken(body.token);
      return { message: 'Login successful', user: decodedToken };
    } catch (error) {
      throw new UnauthorizedException('Invalid token or login failed');
    }
  }

  @Public()
  @Post('register')
  @UsePipes(new ZodValidationPipe(RegisterSchema))
  async register(@Body() body: { phoneNumber: string; name: string }) {
    try {
      // 1. Create user in Firebase Authentication
      const userRecord = await this.authService.createUserWithPhoneNumber(
        body.phoneNumber,
      );

      // Default role assignment
      const role = USER_ROLES.CUSTOMER;

      // 2. Store user details in Firestore
      const newUser: User = {
        id: userRecord.uid,
        name: body.name,
        phone: body.phoneNumber,
        role,
      };
      await this.firestoreService.createWithId(
        COLLECTION_NAMES.USERS,
        userRecord.uid,
        newUser,
      );

      // 3. Set custom claims for the user (role)
      await this.authService.setCustomUserClaims(userRecord.uid, {
        role,
      });

      return {
        message: 'Registration successful',
        user: { uid: userRecord.uid, role },
      };
    } catch (error) {
      throw new UnauthorizedException(`Registration failed: ${error.message}`);
    }
  }
}
