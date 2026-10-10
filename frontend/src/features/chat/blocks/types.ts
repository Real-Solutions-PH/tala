import type { Block } from '../../../api/types'

export type Of<T extends Block['type']> = Extract<Block, { type: T }>
