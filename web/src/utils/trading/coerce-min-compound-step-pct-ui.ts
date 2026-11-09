import {
  COMPOUND_MIN_COMPOUND_STEP_PCT,
  COMPOUND_MIN_STEP_PCT_OFF_VALUE,
  COMPOUND_MIN_STEP_PCT_UI_MAX,
} from '@/utils/constants/trading';

/**
 * Clamps min compound step % from ``NumberInput`` for backtest / compare / hub UIs.
 * Matches trade ladder floor grain (``COMPOUND_MIN_COMPOUND_STEP_PCT``) and UI cap.
 */
export function coerceMinCompoundStepPctFromNumberInput(value: number | null | undefined): number {
  return Math.min(
    COMPOUND_MIN_STEP_PCT_UI_MAX,
    Math.max(COMPOUND_MIN_STEP_PCT_OFF_VALUE, value ?? COMPOUND_MIN_STEP_PCT_OFF_VALUE)
  );
}

export const COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS = {
  min: COMPOUND_MIN_STEP_PCT_OFF_VALUE,
  max: COMPOUND_MIN_STEP_PCT_UI_MAX,
  step: COMPOUND_MIN_COMPOUND_STEP_PCT,
} as const;
