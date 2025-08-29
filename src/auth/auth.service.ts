import { Injectable, UnauthorizedException } from '@nestjs/common';
import { FirebaseService } from '../shared/firebase.service';
import * as admin from 'firebase-admin';
import { User } from '../users/schemas/user.schema';

@Injectable()
export class AuthService {
  constructor(private readonly firebaseService: FirebaseService) {}

  async verifyToken(token: string): Promise<admin.auth.DecodedIdToken & { role?: string }> {
    if (!token) {
      throw new UnauthorizedException('No token provided');
    }

    try {
      const cleanToken = token.startsWith('Bearer ') ? token.substring(7) : token;
      const decodedToken = await this.firebaseService.getAuth().verifyIdToken(cleanToken);
      
      // Attach role from custom claims if available
      if (decodedToken.customClaims && decodedToken.customClaims.role) {
        (decodedToken as admin.auth.DecodedIdToken & { role?: string }).role = decodedToken.customClaims.role;
      }
      
      return decodedToken as admin.auth.DecodedIdToken & { role?: string };
    } catch (error) {
      throw new UnauthorizedException('Invalid token');
    }
  }

  async getUserById(uid: string): Promise<admin.auth.UserRecord> {
    try {
      const user = await this.firebaseService.getAuth().getUser(uid);
      return user;
    } catch (error) {
      throw new UnauthorizedException('User not found');
    }
  }

  async generateCustomToken(uid: string): Promise<string> {
    try {
      const customToken = await this.firebaseService.getAuth().createCustomToken(uid);
      return customToken;
    } catch (error) {
      throw new Error('Failed to generate custom token');
    }
  }

  async setCustomUserClaims(uid: string, claims: { role: string }): Promise<void> {
    try {
      await this.firebaseService.getAuth().setCustomUserClaims(uid, claims);
    } catch (error) {
      throw new Error(`Failed to set custom user claims: ${error.message}`);
    }
  }
}