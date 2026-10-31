import { describe, expect, it } from 'vitest'
import { STRINGS, t } from './i18n.js'
import { editAadhaar, formatAadhaar, validateAadhaar } from './validate.js'
import { isFree, shortFee } from '../components/Icon.jsx'
import { POLICIES } from '../pages/policies.js'

describe('Aadhaar check (runs only in the browser - never sent to the server)', () => {
  it('accepts a checksum-valid number and masks it', () => {
    const r = validateAadhaar('2341 2341 2346')
    expect(r.ok).toBe(true)
    expect(r.message).toContain('2346')
    expect(r.message).not.toContain('2341 2341')
  })
  it('rejects bad checksum, wrong length and numbers starting with 0/1', () => {
    expect(validateAadhaar('234123412347').ok).toBe(false)
    expect(validateAadhaar('23412341234').ok).toBe(false)
    expect(validateAadhaar('123412341234').ok).toBe(false)
  })
  it("explains what to do, in the user's language", () => {
    expect(validateAadhaar('2341 2341 234').message).toBe('11 of 12 digits entered.')
    expect(validateAadhaar('234123412347').message).toContain('two digits are swapped')
    expect(validateAadhaar('234123412347', 'te').message).toContain('ఆధార్')
    expect(validateAadhaar('2341 2341 2346', 'hi').ok).toBe(true)
  })
  it('keeps the cursor in place when fixing a digit in the middle', () => {
    // Typo in the 7th digit: delete it (cursor after it) then type the right digit.
    let r = editAadhaar('9999 4155 7058', '9999 415 7058', 7, 'deleteContentBackward')
    expect(r).toEqual({ value: '9999 4157 058', caret: 7 })
    r = editAadhaar(r.value, '9999 4100057 058'.replace('0005', '05'), 8, 'insertText')  // '0' typed at the cursor
    expect(r.value).toBe('9999 4105 7058')
    expect(validateAadhaar(r.value).ok).toBe(true)
  })
  it('deleting next to a space removes the neighbouring digit', () => {
    expect(editAadhaar('9999 4105 7058', '99994105 7058', 4, 'deleteContentBackward')).toEqual({ value: '9994 1057 058', caret: 3 })
    expect(editAadhaar('9999 4105 7058', '9999 4105 7058'.slice(0, 4) + '4105 7058', 4, 'deleteContentForward').value).toBe('9999 1057 058')
  })
  it('groups digits like the card and ignores other characters', () => {
    expect(formatAadhaar('2341a23412346999')).toBe('2341 2341 2346')
    expect(formatAadhaar('23412')).toBe('2341 2')
  })
})

describe('fee labels', () => {
  it('shows official ₹ amounts and localised fallbacks', () => {
    expect(shortFee([{ amount: '₹50 (incl. taxes)' }, { amount: '₹959' }], 'en')).toBe('₹50+')
    expect(shortFee([{ amount: 'Free' }], 'te')).toBe('ఉచితం')
    expect(shortFee([{ amount: 'Shown on the official payment page before you pay' }], 'hi')).toBe('शुल्क भुगतान पेज पर')
    expect(isFree([{ amount: 'मुफ़्त' }])).toBe(true)
  })
})

describe('translations are complete', () => {
  const en = Object.keys(STRINGS.en)
  for (const lang of ['hi', 'te']) {
    it(`${lang} has every English UI label`, () => {
      const missing = en.filter((k) => !(k in STRINGS[lang]))
      expect(missing).toEqual([])
    })
    it(`${lang} policy pages exist with the same sections`, () => {
      for (const page of Object.values(POLICIES)) {
        expect(page[lang]).toBeTruthy()
        expect(page[lang][1].length).toBe(page.en[1].length)
      }
    })
  }
  it('falls back to English for unknown languages', () => {
    expect(t('xx', 'home')).toBe('Home')
  })
})
