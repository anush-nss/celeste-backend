import {
  Controller,
  Get,
  Param,
  Query,
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { StoresService } from './stores.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import { NearbyStoresQuerySchema, StoreQuerySchema } from './schemas/store.schema';
import { COLLECTION_NAMES } from '../shared/constants';

@ApiTags(COLLECTION_NAMES.STORES)
@Controller(COLLECTION_NAMES.STORES)
export class StoresController extends BaseController {
  constructor(
    private readonly storesService: StoresService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get all stores
  @Public()
  @Get()
  @UsePipes(new ZodValidationPipe(StoreQuerySchema))
  async findAll(@Query() query: any) {
    this.logInfo('Fetching all stores');
    const stores = this.storesService.findAll(query);
    return this.formatResponse(stores, 'Stores retrieved successfully');
  }

  // Get a specific store by ID
  @Public()
  @Get(':id')
  @UsePipes(new ZodValidationPipe(StoreQuerySchema))
  async findOne(@Param('id') id: string, @Query() query: any) {
    this.logInfo(`Fetching store with ID: ${id}`);
    const store = this.storesService.findOne(id, query);
    return this.formatResponse(store, 'Store retrieved successfully');
  }

  // Get nearby stores based on location
  @Public()
  @Get('nearby')
  async findNearby(
    @Query(new ZodValidationPipe(NearbyStoresQuerySchema)) query: any,
  ) {
    this.logInfo('Fetching nearby stores');
    const stores = this.storesService.findNearby(query);
    return this.formatResponse(stores, 'Nearby stores retrieved successfully');
  }
}