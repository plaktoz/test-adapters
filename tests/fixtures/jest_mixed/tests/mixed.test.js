describe('Mixed', () => {
  test('passes one', () => {
    expect(1 + 1).toBe(2);
  });
  test('passes two', () => {
    expect('a').toBe('a');
  });
  test('passes three', () => {
    expect(true).toBe(true);
  });
  test('fails here', () => {
    expect(1 + 1).toBe(3);
  });
  test.skip('is skipped', () => {});
});
