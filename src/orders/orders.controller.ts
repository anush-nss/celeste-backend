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
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { OrdersService } from './orders.service';
import { BaseController } from '../shared/controllers/base.controller';
import { AppLoggerService } from '../shared/logger/logger.service';
import { Roles } from '../auth/roles.decorator';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import {
  CreateOrderSchema,
  UpdateOrderSchema,
  type CreateOrderDto,
  type UpdateOrderDto,
} from './schemas/order.schema';

@ApiTags(COLLECTION_NAMES.ORDERS)
@Controller(COLLECTION_NAMES.ORDERS)
export class OrdersController extends BaseController {
  constructor(
    private readonly ordersService: OrdersService,
    logger: AppLoggerService,
  ) {
    super(logger);
  }

  // Get user orders
  @Get()
  @Roles(USER_ROLES.CUSTOMER)
  async findAll(@Query() query: Record<string, any>) {
    this.logInfo('Fetching all orders');
    const orders = this.ordersService.findAll(query);
    return this.formatResponse(orders, 'Orders retrieved successfully');
  }

  // Get order by ID
  @Get(':id')
  @Roles(USER_ROLES.CUSTOMER)
  async findOne(@Param('id') id: string) {
    this.logInfo(`Fetching order with ID: ${id}`);
    const order = this.ordersService.findOne(id);
    return this.formatResponse(order, 'Order retrieved successfully');
  }

  // Create a new order
  @Post()
  @Roles(USER_ROLES.CUSTOMER)
  @UsePipes(new ZodValidationPipe(CreateOrderSchema))
  async create(@Body() createOrderDto: CreateOrderDto) {
    this.logInfo('Creating new order');
    const order = this.ordersService.create(createOrderDto);
    return this.formatResponse(order, 'Order created successfully');
  }

  // Update order status
  @Put(':id')
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(UpdateOrderSchema))
  async update(
    @Param('id') id: string,
    @Body() updateOrderDto: UpdateOrderDto,
  ) {
    this.logInfo(`Updating order with ID: ${id}`);
    const order = this.ordersService.update(id, updateOrderDto);
    return this.formatResponse(order, 'Order updated successfully');
  }

  // Delete order
  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    this.logInfo(`Deleting order with ID: ${id}`);
    const result = this.ordersService.remove(id);
    return this.formatResponse(result, 'Order deleted successfully');
  }
}
