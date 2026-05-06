export type Helper<T, U> = (input: T) => U;

export type AsyncHelper<T, U> = (input: T) => Promise<U>;
