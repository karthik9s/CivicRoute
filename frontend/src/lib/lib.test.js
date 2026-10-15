import { describe, expect, it } from 'vitest'
import { STRINGS, t } from './i18n.js'
import { validateAadhaar } from './validate.js'
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
