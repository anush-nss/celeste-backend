import {
  Controller,
  Get,
  Param,
  Query,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { FeaturedService } from './featured.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';

@ApiTags('featured')
@Controller('featured')
export class FeaturedController extends BaseController {
  constructor(
    private readonly featuredService: FeaturedService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get all featured products
  @Public()
  @Get()
  async findAll(@Query() query: any) {
    this.logInfo('Fetching all featured products');
    const featured = this.featuredService.findAll(query);
    return this.formatResponse(featured, 'Featured products retrieved successfully');
  }

  // Get a specific featured product by ID
  @Public()
  @Get(':id')
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching featured product with ID: ${id}`);
    const featured = this.featuredService.findOne(id);
    return this.formatResponse(featured, 'Featured product retrieved successfully');
  }
}