function assert(condition: any, message?: string) {
  if (!condition) {
    throw new Error(`Assertion Failed: ${message || 'Expected condition to be truthy'}`);
  }
}

const allowedOrigins = [
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://localhost:8000',
  'http://127.0.0.1:8000',
  'http://localhost:8001',
  'http://127.0.0.1:8001',
  'tauri://localhost',
  'http://tauri.localhost',
  'https://tauri.localhost',
];

interface MockEvent {
  origin: string;
  source: any;
  data: any;
}

function processOAuthMessage(
  event: MockEvent,
  expectedPopup: any,
  onSuccess: (code: string) => void,
  onError: (error: string) => void,
): boolean {
  // 1. Strict Origin Validation
  if (!event.origin || !allowedOrigins.includes(event.origin)) {
    return false;
  }

  // 2. Strict Source Validation
  if (expectedPopup && event.source !== expectedPopup) {
    return false;
  }

  // 3. Payload Type Validation
  if (!event.data || typeof event.data !== 'object') {
    return false;
  }

  if (event.data.type === 'ADFIP_OAUTH_SUCCESS') {
    // 4. Strict Code Payload Validation
    if (typeof event.data.code !== 'string' || event.data.code.length < 16 || event.data.code.length > 256) {
      return false;
    }
    onSuccess(event.data.code);
    return true;
  }

  if (event.data.type === 'ADFIP_OAUTH_ERROR') {
    // 5. Strict Error Payload Validation
    if (typeof event.data.error !== 'string' || event.data.error.length > 500) {
      return false;
    }
    onError(event.data.error);
    return true;
  }

  return false;
}

export function runOAuthMessageTests() {
  console.log('Running ADFIP OAuth Popup Message Handler Verification Suite...\n');

  const mockPopup = { name: 'popup_window_ref' };
  let exchangedCode: string | null = null;
  let receivedError: string | null = null;

  const resetState = () => {
    exchangedCode = null;
    receivedError = null;
  };

  // Test 1: Untrusted origin is ignored
  resetState();
  const test1Handled = processOAuthMessage(
    { origin: 'http://malicious-attacker.com', source: mockPopup, data: { type: 'ADFIP_OAUTH_SUCCESS', code: 'valid_ticket_1234567890_test' } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(!test1Handled, 'Untrusted origin must be rejected');
  assert(exchangedCode === null, 'Code must not be exchanged for untrusted origin');
  console.log('✓ Test 1: Untrusted origin rejected');

  // Test 2: Mismatched event source is ignored
  resetState();
  const otherWindow = { name: 'other_window' };
  const test2Handled = processOAuthMessage(
    { origin: 'http://localhost:5173', source: otherWindow, data: { type: 'ADFIP_OAUTH_SUCCESS', code: 'valid_ticket_1234567890_test' } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(!test2Handled, 'Mismatched event source must be rejected');
  assert(exchangedCode === null, 'Code must not be exchanged for mismatched source');
  console.log('✓ Test 2: Mismatched event source rejected');

  // Test 3: Unknown message type is ignored
  resetState();
  const test3Handled = processOAuthMessage(
    { origin: 'http://localhost:5173', source: mockPopup, data: { type: 'UNKNOWN_OR_MALICIOUS_EVENT', code: 'ticket_code_12345678' } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(!test3Handled, 'Unknown message type must be ignored');
  assert(exchangedCode === null, 'No action taken on unknown message type');
  console.log('✓ Test 3: Unknown message type ignored');

  // Test 4: Missing or non-string code payload is ignored
  resetState();
  const test4Handled = processOAuthMessage(
    { origin: 'http://localhost:5173', source: mockPopup, data: { type: 'ADFIP_OAUTH_SUCCESS', code: 12345 } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(!test4Handled, 'Non-string code payload must be rejected');
  assert(exchangedCode === null, 'No action on non-string code');
  console.log('✓ Test 4: Non-string code payload rejected');

  // Test 5: Empty or too short code payload is ignored
  resetState();
  const test5Handled = processOAuthMessage(
    { origin: 'http://localhost:5173', source: mockPopup, data: { type: 'ADFIP_OAUTH_SUCCESS', code: 'short' } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(!test5Handled, 'Too short code payload must be rejected');
  assert(exchangedCode === null, 'No action on short code');
  console.log('✓ Test 5: Short code payload rejected');

  // Test 6: Valid success message with popup source and trusted origin initiates exchange
  resetState();
  const validTicket = 'valid_oauth_exchange_ticket_random_64_bytes_test';
  const test6Handled = processOAuthMessage(
    { origin: 'http://localhost:5173', source: mockPopup, data: { type: 'ADFIP_OAUTH_SUCCESS', code: validTicket } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(test6Handled, 'Valid message must be processed');
  assert(exchangedCode === validTicket, 'Exchange code must be extracted');
  console.log('✓ Test 6: Valid success message processed and triggers code exchange');

  // Test 7: Valid error message with popup source and trusted origin is handled safely
  resetState();
  const test7Handled = processOAuthMessage(
    { origin: 'http://localhost:8000', source: mockPopup, data: { type: 'ADFIP_OAUTH_ERROR', error: 'User cancelled Google consent' } },
    mockPopup,
    (c) => { exchangedCode = c; },
    (e) => { receivedError = e; },
  );
  assert(test7Handled, 'Valid error message must be processed');
  assert(receivedError === 'User cancelled Google consent', 'Error message must be safely captured');
  console.log('✓ Test 7: Valid error message captured safely');

  console.log('\nAll 7 Popup Message Handler Security Tests Successfully Verified!\n');
  return true;
}

runOAuthMessageTests();
