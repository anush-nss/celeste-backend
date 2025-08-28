import { Injectable, OnModuleInit } from '@nestjs/common';
import * as admin from 'firebase-admin';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class FirebaseService implements OnModuleInit {
  private firebaseApp: admin.app.App | null = null;

  constructor(private configService: ConfigService) {}

  async onModuleInit() {
    // Initialize Firebase Admin SDK
    if (!admin.apps.length) {
      try {
        // Try to initialize with service account key
        const serviceAccountPath = this.configService.get<string>('GOOGLE_APPLICATION_CREDENTIALS');
        
        if (serviceAccountPath && serviceAccountPath !== 'path/to/service-account-key.json') {
          // If we have a valid service account path, use it
          this.firebaseApp = admin.initializeApp({
            credential: admin.credential.cert(serviceAccountPath),
            projectId: this.configService.get<string>('FIREBASE_PROJECT_ID'),
          });
        } else {
          // Fall back to default credentials (for development environments)
          this.firebaseApp = admin.initializeApp({
            credential: admin.credential.applicationDefault(),
            projectId: this.configService.get<string>('FIREBASE_PROJECT_ID'),
          });
        }
      } catch (error) {
        console.warn('Failed to initialize Firebase with service account, falling back to default credentials:', error.message);
        try {
          // Last resort: initialize with default credentials
          this.firebaseApp = admin.initializeApp({
            credential: admin.credential.applicationDefault(),
            projectId: this.configService.get<string>('FIREBASE_PROJECT_ID'),
          });
        } catch (fallbackError) {
          console.error('Failed to initialize Firebase with default credentials:', fallbackError.message);
          throw fallbackError;
        }
      }
    } else {
      this.firebaseApp = admin.app();
    }
  }

  getAuth(): admin.auth.Auth {
    if (!this.firebaseApp) {
      throw new Error('Firebase app not initialized');
    }
    return admin.auth();
  }

  getFirestore(): admin.firestore.Firestore {
    if (!this.firebaseApp) {
      throw new Error('Firebase app not initialized');
    }
    return admin.firestore();
  }

  getApp(): admin.app.App {
    if (!this.firebaseApp) {
      throw new Error('Firebase app not initialized');
    }
    return this.firebaseApp;
  }
}
