// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  COMPOUND_MIN_COMPOUND_STEP_PCT,
  COMPOUND_MIN_STEP_PCT_OFF_VALUE,
  COMPOUND_MIN_STEP_PCT_UI_MAX,
} from '@/utils/constants/trading';
import {
  coerceMinCompoundStepPctFromNumberInput,
  COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS,
} from '@/utils/trading/coerce-min-compound-step-pct-ui';

describe('coerceMinCompoundStepPctFromNumberInput', () => {
  it('clamps to UI max', () => {
    expect(coerceMinCompoundStepPctFromNumberInput(COMPOUND_MIN_STEP_PCT_UI_MAX + 10)).toBe(
      COMPOUND_MIN_STEP_PCT_UI_MAX
    );
  });

  it('clamps nullish to off value', () => {
    expect(coerceMinCompoundStepPctFromNumberInput(null)).toBe(COMPOUND_MIN_STEP_PCT_OFF_VALUE);
    expect(coerceMinCompoundStepPctFromNumberInput(undefined)).toBe(
      COMPOUND_MIN_STEP_PCT_OFF_VALUE
    );
  });

  it('clamps below off value', () => {
    expect(coerceMinCompoundStepPctFromNumberInput(-5)).toBe(COMPOUND_MIN_STEP_PCT_OFF_VALUE);
  });

  it('passes through in-range values', () => {
    expect(coerceMinCompoundStepPctFromNumberInput(2.5)).toBe(2.5);
  });
});

describe('COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS', () => {
  it('matches trading compound step SoT', () => {
    expect(COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS.min).toBe(COMPOUND_MIN_STEP_PCT_OFF_VALUE);
    expect(COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS.max).toBe(COMPOUND_MIN_STEP_PCT_UI_MAX);
    expect(COMPOUND_MIN_STEP_PCT_NUMBER_INPUT_PROPS.step).toBe(COMPOUND_MIN_COMPOUND_STEP_PCT);
  });
});
