// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { EXCHANGES_ENDPOINT } from '@/config/api';
import {
  buildExchangeConnectUrl,
  buildExchangeConnectionUrl,
  buildExchangeLeverageTiersUrl,
  buildExchangesConnectionsListUrl,
  buildExchangesSupportedUrl,
  buildExchangeVerifyUrl,
} from '@/config/exchangeUrls';

describe('exchangeUrls', () => {
  it('builds paths under EXCHANGES_ENDPOINT (SoT)', () => {
    expect(buildExchangesSupportedUrl()).toBe(`${EXCHANGES_ENDPOINT}/supported`);
    expect(buildExchangesConnectionsListUrl()).toBe(EXCHANGES_ENDPOINT);
    expect(buildExchangeConnectUrl()).toBe(`${EXCHANGES_ENDPOINT}/connect`);
    expect(buildExchangeConnectionUrl('conn-1')).toBe(`${EXCHANGES_ENDPOINT}/conn-1`);
    expect(buildExchangeVerifyUrl('c2')).toBe(`${EXCHANGES_ENDPOINT}/c2/verify`);
    expect(buildExchangeLeverageTiersUrl('cx', 'BTC/USDT')).toBe(
      `${EXCHANGES_ENDPOINT}/cx/leverage-tiers?symbol=BTC%2FUSDT`
    );
  });

  it('encodes connection id for path segments', () => {
    expect(buildExchangeConnectionUrl('a/b')).toBe(`${EXCHANGES_ENDPOINT}/a%2Fb`);
    expect(buildExchangeVerifyUrl('a/b')).toBe(`${EXCHANGES_ENDPOINT}/a%2Fb/verify`);
  });
});
