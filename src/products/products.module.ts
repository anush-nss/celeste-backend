import { Module } from '@nestjs/common';
import { ProductsController } from './products.controller';
import { ProductsService } from './products.service';
import { FeaturedController } from './featured.controller';
import { FeaturedService } from './featured.service';
import { SharedModule } from '../shared/shared.module';

@Module({
  imports: [SharedModule],
  controllers: [ProductsController, FeaturedController],
  providers: [ProductsService, FeaturedService],
  exports: [ProductsService, FeaturedService],
})
export class ProductsModule {}