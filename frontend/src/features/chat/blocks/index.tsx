import type { Block } from '../../../api/types'
import { CardBlock } from './CardBlock'
import { ChartBlock } from './ChartBlock'
import { DisclaimerBlock } from './DisclaimerBlock'
import { DocumentBlock } from './DocumentBlock'
import { FormAnswersBlock } from './FormAnswersBlock'
import { LabTableBlock } from './LabTableBlock'
import { MedListBlock } from './MedListBlock'
import { ProfileFieldsBlock } from './ProfileFieldsBlock'
import { RefusalBlock } from './RefusalBlock'

/** One rich block under the answer text. Unknown types render nothing. */
export function BlockView({ block }: { block: Block }) {
  switch (block?.type) {
    case 'card': return <CardBlock block={block} />
    case 'profile_fields': return <ProfileFieldsBlock block={block} />
    case 'med_list': return <MedListBlock block={block} />
    case 'lab_table': return <LabTableBlock block={block} />
    case 'chart': return <ChartBlock block={block} />
    case 'document': return <DocumentBlock block={block} />
    case 'form_answers': return <FormAnswersBlock block={block} />
    case 'disclaimer': return <DisclaimerBlock />
    case 'refusal': return <RefusalBlock block={block} />
    default: return null
  }
}
