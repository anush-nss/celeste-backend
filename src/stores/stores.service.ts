import { Injectable } from '@nestjs/common';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Store, StoreQuery } from './schemas/store.schema';
import { FirestoreService } from '../shared/firestore.service';
import { COLLECTION_NAMES } from '../shared/constants';
import { Inventory } from '../inventory/schemas/inventory.schema';

@Injectable()
export class StoresService {
  constructor(
    private readonly logger: AppLoggerService,
    private readonly firestore: FirestoreService,
  ) {}

  // Find all stores with optional filtering
  async findAll(query: StoreQuery): Promise<Store[]> {
    this.logger.log('Finding all stores', StoresService.name);
    try {
      const { includeInventory, ...filters } = query;
      const stores = await this.firestore.getAll(COLLECTION_NAMES.STORES, filters) as Store[];

      if (includeInventory) {
        const storeIds = stores.map((s) => s.id);
        const inventory = await this.firestore.getAll(COLLECTION_NAMES.INVENTORY, {
          storeId: storeIds,
        }) as Inventory[];

        stores.forEach((store) => {
          store.inventory = inventory.filter((item) => item.storeId === store.id);
        });
      }

      return stores;
    } catch (error) {
      this.logger.error(`Failed to fetch stores: ${error.message}`, error.stack, StoresService.name);
      throw error;
    }
  }

  // Find a specific store by ID
  async findOne(id: string, query: StoreQuery): Promise<Store | null> {
    this.logger.log(`Finding store with ID: ${id}`, StoresService.name);
    try {
      const store = await this.firestore.getById(COLLECTION_NAMES.STORES, id) as Store;
      if (!store) {
        return null;
      }

      if (query.includeInventory) {
        const inventory = await this.firestore.getAll(COLLECTION_NAMES.INVENTORY, {
          storeId: store.id,
        }) as Inventory[];
        store.inventory = inventory;
      }

      return store;
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
      const stores = await this.firestore.getAll(COLLECTION_NAMES.STORES, query);
      return stores as Store[];
    } catch (error) {
      this.logger.error(`Failed to fetch nearby stores: ${error.message}`, error.stack, StoresService.name);
      throw error;
    }
  }
}