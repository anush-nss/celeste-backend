import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Param,
  Body,
  Query,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { OrdersService } from './orders.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';

@ApiTags('orders')
@Controller('orders')
export class OrdersController extends BaseController {
  constructor(
    private readonly ordersService: OrdersService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get user orders
  @Get()
  async findAll(@Query() query: any) {
    this.logInfo('Fetching all orders');
    const orders = this.ordersService.findAll(query);
    return this.formatResponse(orders, 'Orders retrieved successfully');
  }

  // Get order by ID
  @Get(':id')
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching order with ID: ${id}`);
    const order = this.ordersService.findOne(id);
    return this.formatResponse(order, 'Order retrieved successfully');
  }

  // Create a new order
  @Post()
  async create(@Body() createOrderDto: any) {
    this.logInfo('Creating new order');
    const order = this.ordersService.create(createOrderDto);
    return this.formatResponse(order, 'Order created successfully');
  }

  // Update order status
  @Put(':id')
  async update(
    @Param('id') id: string,
    @Body() updateOrderDto: any,
  ) {
    this.logInfo(`Updating order with ID: ${id}`);
    const order = this.ordersService.update(id, updateOrderDto);
    return this.formatResponse(order, 'Order updated successfully');
  }

  // Delete order
  @Delete(':id')
  async remove(@Param('id') id: string) {
    this.logInfo(`Deleting order with ID: ${id}`);
    const result = this.ordersService.remove(id);
    return this.formatResponse(result, 'Order deleted successfully');
  }
}