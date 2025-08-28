import {
  Controller,
  Get,
  Param,
  Query,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { ProductsService } from './products.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Public } from '../auth/public.decorator';

@ApiTags('products')
@Controller('products')
export class ProductsController extends BaseController {
  constructor(
    private readonly productsService: ProductsService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get all products with optional filtering
  @Public()
  @Get()
  async findAll(@Query() query: any) {
    this.logInfo('Fetching all products');
    const products = this.productsService.findAll(query);
    return this.formatResponse(products, 'Products retrieved successfully');
  }

  // Get a specific product by ID
  @Public()
  @Get(':id')
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching product with ID: ${id}`);
    const product = this.productsService.findOne(id);
    return this.formatResponse(product, 'Product retrieved successfully');
  }
}