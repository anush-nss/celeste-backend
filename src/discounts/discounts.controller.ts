import {
  Controller,
  Get,
  Param,
  Query,
  Post,
  Put,
  Delete,
  Body,
  UsePipes,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';
import { Roles } from '../auth/roles.decorator';
import { USER_ROLES, COLLECTION_NAMES } from '../shared/constants';
import { DiscountsService } from './discounts.service';
import { ZodValidationPipe } from '../shared/pipes/zod-validation.pipe';
import type {
  CreateDiscountDto,
  UpdateDiscountDto,
  DiscountQueryDto,
} from './schemas/discount.schema';
import { CreateDiscountSchema, UpdateDiscountSchema, DiscountQuerySchema } from './schemas/discount.schema';

@ApiTags(COLLECTION_NAMES.DISCOUNTS)
@Controller(COLLECTION_NAMES.DISCOUNTS)
export class DiscountsController {
  constructor(private readonly discountsService: DiscountsService) {}

  // Get all discounts
  @Public()
  @Get()
  @UsePipes(new ZodValidationPipe(DiscountQuerySchema))
  async findAll(@Query() query: DiscountQueryDto) {
    const discounts = await this.discountsService.findAll(query);
    return discounts;
  }

  // Get a specific discount by ID
  @Public()
  @Get(':id')
  async findOne(@Param('id') id: string) {
    const discount = await this.discountsService.findOne(id);
    return discount;
  }

  // Create a new discount
  @Post()
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(CreateDiscountSchema))
  async create(@Body() createDiscountDto: CreateDiscountDto) {
    const discount = await this.discountsService.create(createDiscountDto);
    return discount;
  }

  // Update a discount
  @Put(':id')
  @Roles(USER_ROLES.ADMIN)
  @UsePipes(new ZodValidationPipe(UpdateDiscountSchema))
  async update(
    @Param('id') id: string,
    @Body() updateDiscountDto: UpdateDiscountDto,
  ) {
    const discount = await this.discountsService.update(id, updateDiscountDto);
    return discount;
  }

  // Delete a discount
  @Delete(':id')
  @Roles(USER_ROLES.ADMIN)
  async remove(@Param('id') id: string) {
    const result = await this.discountsService.remove(id);
    return result;
  }
}