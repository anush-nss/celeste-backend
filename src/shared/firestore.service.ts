import { Injectable } from '@nestjs/common';
import { FirebaseService } from './firebase.service';
import * as admin from 'firebase-admin';

@Injectable()
export class FirestoreService {
  private db: admin.firestore.Firestore | null = null;

  constructor(private readonly firebaseService: FirebaseService) {
    // Initialize Firestore after Firebase app is ready
    this.initializeFirestore();
  }

  private initializeFirestore() {
    try {
      this.db = this.firebaseService.getFirestore();
    } catch (error) {
      console.warn('Firestore not yet initialized, will retry when needed');
    }
  }

  public getDb(): admin.firestore.Firestore {
    if (!this.db) {
      this.db = this.firebaseService.getFirestore();
    }
    return this.db;
  }

  getCollection(collectionName: string) {
    return this.getDb().collection(collectionName);
  }

  async getAll(collectionName: string, query?: Record<string, any>) {
    let ref: admin.firestore.Query = this.getDb().collection(collectionName);
    
    // Apply filters if provided
    if (query) {
      Object.keys(query).forEach(key => {
        if (key !== 'limit' && key !== 'offset' && key !== 'sortBy' && key !== 'order') {
          ref = ref.where(key, '==', query[key]);
        }
      });
      
      // Apply ordering
      if (query.sortBy) {
        ref = ref.orderBy(query.sortBy, query.order === 'desc' ? 'desc' : 'asc');
      }
      
      // Apply limits
      if (query.limit) {
        ref = ref.limit(Number(query.limit));
      }
    }
    
    const snapshot = await ref.get();
    return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
  }

  async getById(collectionName: string, id: string) {
    const doc = await this.getDb().collection(collectionName).doc(id).get();
    if (!doc.exists) {
      return null;
    }
    return { id: doc.id, ...doc.data() };
  }

  async create(collectionName: string, data: Record<string, any>) {
    const docRef = await this.getDb().collection(collectionName).add({
      ...data,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    return { id: docRef.id, ...data };
  }

  async createWithId(collectionName: string, id: string, data: Record<string, any>) {
    await this.getDb().collection(collectionName).doc(id).set({
      ...data,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    return { id, ...data };
  }

  async update(collectionName: string, id: string, data: Record<string, any>) {
    await this.getDb().collection(collectionName).doc(id).update({
      ...data,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    return { id, ...data };
  }

  async delete(collectionName: string, id: string) {
    await this.getDb().collection(collectionName).doc(id).delete();
    return { id };
  }
}