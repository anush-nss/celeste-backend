import { Injectable } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Store } from './schemas/store.schema';
import { FirestoreService } from '../shared/firestore.service';

@Injectable()
export class StoresService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  // Find all stores with optional filtering
  async findAll(query: any): Promise<Store[]> {
    this.logger.log('Finding all stores', StoresService.name);
    try {
      const stores = await this.firestore.getAll('stores', query);
      return stores as Store[];
    } catch (error) {
      this.logger.error(`Failed to fetch stores: ${error.message}`, error.stack, StoresService.name);
      throw error;
    }
  }

  // Find a specific store by ID
  async findOne(id: string): Promise<Store | null> {
    this.logger.log(`Finding store with ID: ${id}`, StoresService.name);
    try {
      const store = await this.firestore.getById('stores', id);
      return store as Store | null;
    } catch (error) {
      this.logger.error(`Failed to fetch store ${id}: ${error.message}`, error.stack, StoresService.name);
      throw error;
    }
  }

  // Find nearby stores based on location
  async findNearby(query: any): Promise<Store[]> {
    this.logger.log('Finding nearby stores', StoresService.name);
    try {
      // This is a simplified implementation
      // In a real application, you would use Firestore's geospatial queries
      // or a library like GeoFirestore for efficient location-based queries
      const stores = await this.firestore.getAll('stores', query);
      return stores as Store[];
    } catch (error) {
      this.logger.error(`Failed to fetch nearby stores: ${error.message}`, error.stack, StoresService.name);
      throw error;
    }
  }
}