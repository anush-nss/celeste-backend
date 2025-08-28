import { z } from 'zod';
import { USER_ROLES } from '../../shared/constants';

export const LoginSchema = z.object({
  token: z.string().min(1),
});

export const RegisterSchema = z.object({
  phoneNumber: z.string().min(1),
  name: z.string().min(1),
});

export type LoginDto = z.infer<typeof LoginSchema>;
export type RegisterDto = z.infer<typeof RegisterSchema>;
