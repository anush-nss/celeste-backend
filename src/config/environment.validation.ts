import { z } from 'zod';

const EnvironmentSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']),
  PORT: z.string().transform(Number).pipe(z.number()),
  DATABASE_URL: z.string(),
  FIREBASE_PROJECT_ID: z.string(),
  FIREBASE_PRIVATE_KEY: z.string(),
  FIREBASE_CLIENT_EMAIL: z.string(),
  JWT_SECRET: z.string(),
});

export function validate(config: Record<string, unknown>) {
  try {
    const validatedConfig = EnvironmentSchema.parse(config);
    return validatedConfig;
  } catch (error) {
    throw new Error(`Config validation error: ${error.errors.map(e => e.message).join(', ')}`);
  }
}