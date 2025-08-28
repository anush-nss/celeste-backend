import { Injectable, UnauthorizedException } from '@nestjs/common';
import { FirebaseService } from '../shared/firebase.service';
import * as admin from 'firebase-admin';

@Injectable()
export class AuthService {
  constructor(private readonly firebaseService: FirebaseService) {}

  async verifyToken(token: string): Promise<admin.auth.DecodedIdToken> {
    if (!token) {
      throw new UnauthorizedException('No token provided');
    }

    try {
      // Remove 'Bearer ' prefix if present
      const cleanToken = token.startsWith('Bearer ') ? token.substring(7) : token;
      const decodedToken = await this.firebaseService.getAuth().verifyIdToken(cleanToken);
      return decodedToken;
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
}