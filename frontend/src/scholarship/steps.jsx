/* Wizard steps for the AU Need Based Financial Grant form (Form 1).
 * Each step: fromApp(app) -> form state, toPayload(form) -> { payload, remap(errors) }, and a Fields component.
 * Section keys match the backend: PATCH /scholarships/applications/{id}/sections/{key}/ */
import {
  blank, fromBoolInput, fromMonthInput, packRows, remapRowErrors, rupees, tableErrors, toBoolInput, toDate,
  toInput, toMonthInput, toNumber,
} from './convert.js'
import { Display, Input, RowsTable, Select, TextArea, YesNo } from './fields.jsx'
import * as O from './options.js'

const pick = (obj, keys) => Object.fromEntries(keys.map((k) => [k, toInput(obj?.[k])]))
const cell = (v) => (v === '' || v === null || v === undefined ? 0 : toNumber(v))
const keep = (errors) => errors

function Totals({ rows }) {
  return (
    <dl className="totals">
      {rows.map(([label, value, strong]) => (
        <div key={label} className={strong ? 'totals-strong' : undefined}>
          <dt>{label}</dt>
          <dd>{rupees(value)}</dd>
        </div>
      ))}
    </dl>
  )
}

// ---------- 1. Personal details (Q1-8) ----------

const PERSONAL = ['registration_id', 'program', 'applicant_name', 'gender', 'marital_status', 'cnic', 'date_of_birth',
  'domicile', 'present_address', 'permanent_address', 'tel_residence', 'mobile']

const personal = {
  key: 'personal',
  title: 'Personal details',
  fromApp: (app) => pick(app, PERSONAL),
  toPayload: (form) => ({ payload: { ...form, date_of_birth: toDate(form.date_of_birth) }, remap: keep }),
  Fields({ form, set, errors, app, disabled }) {
    const p = { form, set, errors, disabled }
    return (
      <div className="grid">
        <Input {...p} name="applicant_name" label="Applicant's name" required />
        <Input {...p} name="registration_id" label="Registration ID" required hint="6 to 8 digits, e.g. 233585" />
        <Input {...p} name="program" label="Degree title / program" required hint="e.g. BS Software Engineering" />
        <Display label="Department" value={app.department} />
        <Select {...p} name="gender" label="Gender" options={O.GENDER} required />
        <Select {...p} name="marital_status" label="Marital status" options={O.MARITAL} required />
        <Input {...p} name="cnic" label="CNIC / B-Form number" required hint="13 digits, e.g. 36302-1234567-1" />
        <Input {...p} name="date_of_birth" label="Date of birth" type="date" required
          hint={app.age != null ? `Age: ${app.age} years` : undefined} />
        <Input {...p} name="domicile" label="Domicile" required hint="District of domicile" />
        <Input {...p} name="mobile" label="Mobile" required hint="03XXXXXXXXX" />
        <Input {...p} name="tel_residence" label="Telephone (residence)" hint="Optional" />
        <Display label="Email" value={app.email} hint="From your account" />
        <Input {...p} name="present_address" label="Present address" required wide />
        <Input {...p} name="permanent_address" label="Permanent address" required wide />
        {!disabled && (
          <label className="checkbox field-wide">
            <input type="checkbox" checked={form.permanent_address !== '' && form.permanent_address === form.present_address}
              onChange={(e) => set('permanent_address', e.target.checked ? form.present_address : '')} />
            Permanent address is the same as present address
          </label>
        )}
      </div>
    )
  },
}

// ---------- 2. Family (Q9, Q11) ----------

const MEMBER_COLS = ['name', 'relationship', 'marital_status', 'remarks']
const STUDYING_COLS = ['name', 'relation', 'institute', 'fee_per_month']

const household = {
  key: 'household',
  title: 'Family',
  fromApp: (app) => ({
    total_family_members: toInput(app.total_family_members),
    household_members: app.household_members.map((r) => pick(r, MEMBER_COLS)),
    studying_members: app.studying_members.map((r) => pick(r, STUDYING_COLS)),
  }),
  toPayload(form) {
    const members = packRows(form.household_members, (r) => blank(r, MEMBER_COLS), (r) => r)
    const studying = packRows(form.studying_members, (r) => blank(r, STUDYING_COLS),
      (r) => ({ ...r, fee_per_month: toNumber(r.fee_per_month) }))
    return {
      payload: {
        total_family_members: toNumber(form.total_family_members),
        household_members: members.payload,
        studying_members: studying.payload,
      },
      remap: (e) => remapRowErrors(remapRowErrors(e, 'household_members', members.origin), 'studying_members', studying.origin),
    }
  },
  Fields({ form, set, errors, app, disabled }) {
    return (
      <>
        <div className="grid">
          <Input form={form} set={set} errors={errors} disabled={disabled} name="total_family_members" type="number"
            label="Total family members currently living with you" required />
        </div>
        <h3>Family members living with you (Q9)</h3>
        <RowsTable rows={form.household_members} setRows={(rows) => set('household_members', rows)} disabled={disabled}
          errors={tableErrors(errors, 'household_members')} addLabel="Add family member"
          makeRow={() => ({ name: '', relationship: '', marital_status: '', remarks: '' })}
          columns={[
            { name: 'name', label: 'Name', width: 160 },
            { name: 'relationship', label: 'Relationship', type: 'select', options: O.RELATIONSHIP },
            { name: 'marital_status', label: 'Marital status', type: 'select', options: O.MARITAL },
            { name: 'remarks', label: 'Remarks', width: 140 },
          ]} />
        <h3>Brothers, sisters, children or family members studying (Q11)</h3>
        <RowsTable rows={form.studying_members} setRows={(rows) => set('studying_members', rows)} disabled={disabled}
          errors={tableErrors(errors, 'studying_members')} addLabel="Add family member studying"
          makeRow={() => ({ name: '', relation: '', institute: '', fee_per_month: '' })}
          columns={[
            { name: 'name', label: 'Name', width: 140 },
            { name: 'relation', label: 'Relation', type: 'select', options: O.RELATIONSHIP },
            { name: 'institute', label: 'Name & address of institute', width: 200 },
            { name: 'fee_per_month', label: 'Fee per month (Rs.)', type: 'money', width: 110 },
          ]} />
        <Totals rows={[['Total fees & tuition charges (11.1)', app.summary.total_studying_fees, true]]} />
      </>
    )
  },
}

// ---------- 3. Parents and guardian (Q12-23) ----------

const PERSON = ['name', 'relationship_to_applicant', 'cnic', 'status', 'profession', 'employer', 'tel_office', 'mobile',
  'occupation_type', 'ntn', 'designation_grade', 'gross_monthly_income', 'net_monthly_income']
const ROLES = ['father', 'mother', 'guardian']

function emptyPerson() {
  return { ...Object.fromEntries(PERSON.map((k) => [k, ''])), status: 'alive' }
}

function Person({ role, title, person, setPerson, errors, disabled }) {
  const p = { form: person, set: setPerson, errors, disabled }
  const alive = role === 'guardian' || person.status !== 'deceased'
  const earning = alive && person.profession && person.profession !== 'not_earning'
  const listError = Array.isArray(errors) ? errors.join(' ') : null
  const fieldErrors = Array.isArray(errors) ? {} : errors
  const q = { ...p, errors: fieldErrors }
  return (
    <fieldset className="person">
      <legend>{title}</legend>
      {listError && <p className="field-error">{listError}</p>}
      <div className="grid">
        <Input {...q} name="name" label="Name" required />
        <Input {...q} name="cnic" label="CNIC" required hint="13 digits" />
        {role === 'guardian'
          ? <Input {...q} name="relationship_to_applicant" label="Relationship to you" required hint="e.g. Uncle" />
          : <Select {...q} name="status" label="Status" options={O.LIFE_STATUS} required />}
        {alive && <Select {...q} name="profession" label="Professional status" options={O.PROFESSION} required />}
        {earning && (
          <>
            <Input {...q} name="employer" label="Name of company / employer / business" />
            <Input {...q} name="occupation_type" label="Occupation type" hint="e.g. Government, Driver, Shopkeeper" />
            <Input {...q} name="designation_grade" label="Designation & grade" hint="e.g. Assistant BPS-15" />
            <Input {...q} name="ntn" label="NTN" hint="Optional" />
            <Input {...q} name="tel_office" label="Telephone (office)" hint="Optional" />
            <Input {...q} name="gross_monthly_income" label="Gross monthly income (Rs.)" type="money" required />
            <Input {...q} name="net_monthly_income" label="Net take-home monthly income (Rs.)" type="money" required
              hint="Salary / pension / other, after deductions" />
          </>
        )}
        {alive && <Input {...q} name="mobile" label="Mobile" hint="Optional, 03XXXXXXXXX" />}
      </div>
    </fieldset>
  )
}

const parents = {
  key: 'parents',
  title: 'Parents & guardian',
  fromApp(app) {
    const byRole = Object.fromEntries(app.parents.map((p) => [p.role, p]))
    const form = Object.fromEntries(ROLES.map((r) => [r, byRole[r] ? { ...emptyPerson(), ...pick(byRole[r], PERSON) } : emptyPerson()]))
    return { ...form, hasGuardian: Boolean(byRole.guardian) }
  },
  toPayload(form) {
    const roles = ROLES.filter((r) => r !== 'guardian' || form.hasGuardian)
    const rows = roles.map((role) => ({
      role,
      ...form[role],
      status: role === 'guardian' ? 'alive' : form[role].status || 'alive',
      gross_monthly_income: toNumber(form[role].gross_monthly_income),
      net_monthly_income: toNumber(form[role].net_monthly_income),
    }))
    return {
      payload: { parents: rows },
      // row errors come back by position; show them under father / mother / guardian instead
      remap(errors) {
        const e = errors?.parents
        if (!e || Array.isArray(e)) return errors
        const byRole = {}
        for (const [index, value] of Object.entries(e)) if (roles[Number(index)]) byRole[roles[Number(index)]] = value
        return { ...errors, ...byRole }
      },
    }
  },
  Fields({ form, set, errors, disabled }) {
    const setPersonFor = (role) => (name, value) => set(role, { ...form[role], [name]: value })
    const fatherDeceased = form.father.status === 'deceased'
    const listError = Array.isArray(errors?.parents) ? errors.parents.join(' ') : null
    return (
      <>
        {listError && <p className="field-error">{listError}</p>}
        <Person role="father" title="Father (Q12-19)" person={form.father} setPerson={setPersonFor('father')}
          errors={errors?.father || {}} disabled={disabled} />
        <Person role="mother" title="Mother (Q20-23)" person={form.mother} setPerson={setPersonFor('mother')}
          errors={errors?.mother || {}} disabled={disabled} />
        {(form.hasGuardian || fatherDeceased) && !form.hasGuardian && !disabled && (
          <p className="notice">A guardian is required because your father is deceased.</p>
        )}
        {form.hasGuardian ? (
          <>
            <Person role="guardian" title="Guardian" person={form.guardian} setPerson={setPersonFor('guardian')}
              errors={errors?.guardian || {}} disabled={disabled} />
            {!disabled && (
              <button type="button" className="link-button" onClick={() => set('hasGuardian', false)}>Remove guardian</button>
            )}
          </>
        ) : (
          !disabled && <button type="button" className="secondary" onClick={() => set('hasGuardian', true)}>Add guardian</button>
        )}
        {errors?.guardian && !form.hasGuardian && <p className="field-error">{[].concat(errors.guardian).join(' ')}</p>}
        <p className="field-hint">
          Each earning parent or guardian will need to sign a stamp-paper income declaration (Form 2). It is prepared
          from these answers.
        </p>
      </>
    )
  },
}

// ---------- 4. Income (Q10, Q24, Q25) ----------

const EARNING_COLS = ['name', 'relationship', 'occupation', 'organization', 'designation', 'gross_pay', 'net_pay', 'remarks']
const HOLDERS = [['father', 'Father'], ['mother', 'Mother'], ['spouse', 'Spouse'], ['self_amount', 'Self'], ['other', 'Other']]
const PROFESSION_LABEL = Object.fromEntries(O.PROFESSION.map((o) => [o.value, o.label]))

const income = {
  key: 'income',
  title: 'Income',
  fromApp(app) {
    const bySource = Object.fromEntries(app.asset_income.map((r) => [r.source, r]))
    return {
      applicant_gross_income: toInput(app.applicant_gross_income),
      applicant_net_income: toInput(app.applicant_net_income),
      earning_members: app.earning_members.map((r) => pick(r, EARNING_COLS)),
      asset_income: O.ASSET_INCOME_SOURCES.map((s) => pick(bySource[s.value] || {}, HOLDERS.map(([k]) => k))),
      asset_income_other_specify: toInput(app.asset_income_other_specify),
    }
  },
  toPayload(form) {
    const earning = packRows(form.earning_members, (r) => blank(r, EARNING_COLS),
      (r) => ({ ...r, gross_pay: toNumber(r.gross_pay), net_pay: toNumber(r.net_pay) }))
    return {
      payload: {
        applicant_gross_income: toNumber(form.applicant_gross_income),
        applicant_net_income: toNumber(form.applicant_net_income),
        earning_members: earning.payload,
        asset_income: form.asset_income.map((row, i) => ({
          source: O.ASSET_INCOME_SOURCES[i].value,
          ...Object.fromEntries(HOLDERS.map(([k]) => [k, cell(row[k])])),
        })),
        asset_income_other_specify: form.asset_income_other_specify,
      },
      remap: (e) => remapRowErrors(e, 'earning_members', earning.origin),
    }
  },
  Fields({ form, set, errors, app, disabled }) {
    const p = { form, set, errors, disabled }
    const listed = new Set(form.earning_members.map((r) => r.relationship))
    const parentsToAdd = app.parents.filter((x) => x.status === 'alive' && (x.gross_monthly_income || 0) > 0 && !listed.has(x.role))
    const addParents = () => set('earning_members', [...form.earning_members, ...parentsToAdd.map((x) => ({
      name: x.name, relationship: x.role, occupation: PROFESSION_LABEL[x.profession] || '', organization: x.employer,
      designation: x.designation_grade, gross_pay: toInput(x.gross_monthly_income), net_pay: toInput(x.net_monthly_income),
      remarks: '',
    }))])
    const s = app.summary
    return (
      <>
        <h3>Family members earning (Q10)</h3>
        <p className="field-hint">Include your parents if they earn. Net pay is the take-home amount after deductions.</p>
        {!disabled && parentsToAdd.length > 0 && (
          <button type="button" className="secondary" onClick={addParents}>
            Add {parentsToAdd.map((x) => x.role).join(' and ')} from the Parents step
          </button>
        )}
        <RowsTable rows={form.earning_members} setRows={(rows) => set('earning_members', rows)} disabled={disabled}
          errors={tableErrors(errors, 'earning_members')} addLabel="Add earning member"
          makeRow={() => Object.fromEntries(EARNING_COLS.map((k) => [k, '']))}
          columns={[
            { name: 'name', label: 'Name', width: 140 },
            { name: 'relationship', label: 'Relationship', type: 'select', options: O.RELATIONSHIP },
            { name: 'occupation', label: 'Occupation', width: 120 },
            { name: 'organization', label: 'Organization', width: 130 },
            { name: 'designation', label: 'Designation', width: 110 },
            { name: 'gross_pay', label: 'Monthly gross (Rs.)', type: 'money', width: 100 },
            { name: 'net_pay', label: 'Monthly net (Rs.)', type: 'money', width: 100 },
            { name: 'remarks', label: 'Remarks', width: 110 },
          ]} />
        <h3>Your own income</h3>
        <div className="grid">
          <Input {...p} name="applicant_gross_income" label="Your monthly gross pay (Rs.)" type="money" required hint="Enter 0 if none" />
          <Input {...p} name="applicant_net_income" label="Your monthly net (take-home) pay (Rs.)" type="money" required hint="Enter 0 if none" />
        </div>
        <h3>Asset income per month (Q24)</h3>
        <RowsTable fixedLabels={O.ASSET_INCOME_SOURCES.map((o) => o.label)} rowHeader="Income source" disabled={disabled}
          rows={form.asset_income} setRows={(rows) => set('asset_income', rows)} errors={tableErrors(errors, 'asset_income')}
          columns={HOLDERS.map(([name, label]) => ({ name, label: `${label} (Rs.)`, type: 'money', width: 90 }))} />
        <div className="grid">
          <Input {...p} name="asset_income_other_specify" label='"Other" asset income is from' hint="Required if you entered an amount in Other" />
        </div>
        <h3>Total family monthly income (Q25)</h3>
        <Totals rows={[
          ['Total monthly family gross earnings (10.1)', s.total_family_earning_gross],
          ['Net (take-home) pay of all earners', s.monthly_net_pay],
          ['Monthly income from assets (24.1)', s.monthly_asset_income],
          ['Total monthly income (25.1) = net pay + asset income', s.total_monthly_income, true],
          ['Total annual income (25.2) = 25.1 x 12', s.total_annual_income],
        ]} />
        <p className="field-hint">Totals are recalculated each time you save.</p>
      </>
    )
  },
}

// ---------- 5. Accommodation (Q26A) ----------

const ACCOMMODATION = ['accommodation_type', 'accommodation_status', 'rent_paid_by', 'plot_size_sqft', 'covered_area_sqft',
  'accommodation_address', 'bedrooms', 'air_conditioners', 'monthly_rent', 'other_house_details']

const accommodation = {
  key: 'accommodation',
  title: 'Accommodation',
  fromApp: (app) => ({ ...pick(app, ACCOMMODATION), other_house_owned: toBoolInput(app.other_house_owned) }),
  toPayload: (form) => ({
    payload: {
      ...form,
      plot_size_sqft: toNumber(form.plot_size_sqft),
      covered_area_sqft: toNumber(form.covered_area_sqft),
      monthly_rent: toNumber(form.monthly_rent),
      other_house_owned: fromBoolInput(form.other_house_owned),
    },
    remap: keep,
  }),
  Fields({ form, set, errors, app, disabled }) {
    const p = { form, set, errors, disabled }
    const rented = form.accommodation_status === 'rented'
    return (
      <>
        <div className="grid">
          <Select {...p} name="accommodation_type" label="Type" options={O.ACCOMMODATION_TYPE} required />
          <Select {...p} name="accommodation_status" label="Status" options={O.ACCOMMODATION_STATUS} required />
          {rented && <Select {...p} name="rent_paid_by" label="Rent paid by" options={O.RENT_PAID_BY} required />}
          {rented && <Input {...p} name="monthly_rent" label="Monthly rent (Rs.)" type="money" required />}
          <Input {...p} name="plot_size_sqft" label="House plot size (sq. ft.)" type="number" required />
          <Input {...p} name="covered_area_sqft" label="Covered area (sq. ft.)" type="number" required />
          <Select {...p} name="bedrooms" label="Number of bedrooms" options={O.BEDROOMS} required />
          <Select {...p} name="air_conditioners" label="Number of air conditioners" options={O.AIR_CONDITIONERS} required />
          <Input {...p} name="accommodation_address" label="Accommodation location / address" required wide />
          <YesNo {...p} name="other_house_owned" label="Do your parents / guardian own any other house or flat?" required wide />
          {form.other_house_owned === 'yes' && (
            <Input {...p} name="other_house_details" label="Location and size of the other house / flat" required wide />
          )}
        </div>
        {rented && (
          <Totals rows={[
            ['Accommodation monthly rent', app.summary.accommodation_monthly_rent],
            ['Accommodation annual rent', app.summary.accommodation_annual_rent],
          ]} />
        )}
      </>
    )
  },
}

// ---------- 6. Expenditure (Q27-31) ----------

const UTILITY_COLS = ['telephone', 'electricity', 'gas', 'water']
const UTILITY_LABELS = ['Most recent month', 'Previous month', 'Month before that']

const expenses = {
  key: 'expenses',
  title: 'Expenditure',
  fromApp(app) {
    const byMonth = Object.fromEntries(app.utility_months.map((r) => [r.month_index, r]))
    return {
      utility_months: [1, 2, 3].map((i) => (byMonth[i] ? pick(byMonth[i], UTILITY_COLS) : pick({}, UTILITY_COLS))),
      ...pick(app, ['medical_monthly', 'misc_monthly', 'negative_income_explanation']),
    }
  },
  toPayload(form) {
    const months = packRows(form.utility_months.map((r, i) => ({ ...r, month_index: i + 1 })),
      (r) => blank(r, UTILITY_COLS), (r) => ({ month_index: r.month_index, ...Object.fromEntries(UTILITY_COLS.map((k) => [k, cell(r[k])])) }))
    return {
      payload: {
        utility_months: months.payload,
        medical_monthly: toNumber(form.medical_monthly),
        misc_monthly: toNumber(form.misc_monthly),
        negative_income_explanation: form.negative_income_explanation,
      },
      remap: (e) => remapRowErrors(e, 'utility_months', months.origin),
    }
  },
  Fields({ form, set, errors, app, disabled }) {
    const p = { form, set, errors, disabled }
    const s = app.summary
    const negative = s.net_monthly_disposable < 0
    return (
      <>
        <h3>Utility bills paid, last three months (Q27)</h3>
        <RowsTable fixedLabels={UTILITY_LABELS} rowHeader="Month" disabled={disabled} rows={form.utility_months}
          setRows={(rows) => set('utility_months', rows)} errors={tableErrors(errors, 'utility_months')}
          columns={UTILITY_COLS.map((name) => ({ name, label: `${name[0].toUpperCase()}${name.slice(1)} (Rs.)`, type: 'money', width: 90 }))} />
        <div className="grid">
          <Input {...p} name="medical_monthly" label="Medical expenditure per month (Q28)" type="money" required
            hint="Average of the last three months. Enter 0 if none." />
          <Input {...p} name="misc_monthly" label="Miscellaneous expenditure per month" type="money" required
            hint="Food, transport and other household spending" />
        </div>
        <h3>Total family expenditure and disposable income (Q29-31)</h3>
        <Totals rows={[
          ['Education (11.1 fees of family members studying)', s.expenditure.education],
          ['Accommodation (rent)', s.expenditure.accommodation],
          ['Utilities (monthly average)', s.expenditure.utilities],
          ['Medical', s.expenditure.medical],
          ['Miscellaneous', s.expenditure.misc],
          ['Total monthly expenditure (29.1)', s.total_monthly_expenditure, true],
          ['Total monthly income (25.1)', s.total_monthly_income],
          ['Net monthly disposable income (30) = 25.1 - 29.1', s.net_monthly_disposable, true],
          ['Net annual disposable income (31) = 30 x 12', s.net_annual_disposable],
        ]} />
        <p className="field-hint">Totals are recalculated each time you save.</p>
        {(negative || form.negative_income_explanation) && (
          <TextArea {...p} name="negative_income_explanation" required={negative}
            label="Your disposable income is negative. Explain the reasons for the gap and how your family meets it." />
        )}
      </>
    )
  },
}

// ---------- 7. Assets and financing (Q32-38) ----------

const VEHICLE_COLS = ['transport_type', 'transport_type_other', 'make_model', 'engine_cc', 'registration_no', 'ownership_period']
const LAND_COLS = ['quantity', 'size', 'location', 'cultivable_area', 'yield_per_acre']
const WORTH = [['father', 'Father'], ['mother', 'Mother'], ['spouse', 'Spouse'], ['self_amount', 'Self'], ['guardian', 'Guardian']]

const assets = {
  key: 'assets',
  title: 'Assets & financing',
  fromApp(app) {
    const land = Object.fromEntries(app.land_holdings.map((r) => [r.category, r]))
    const worth = Object.fromEntries(app.asset_worth.map((r) => [r.title, r]))
    return {
      owns_transport: toBoolInput(app.owns_transport),
      vehicles: app.vehicles.map((r) => pick(r, VEHICLE_COLS)),
      ...pick(app, ['cattle_count', 'cattle_kind', 'education_loan_details', 'other_financing', 'admission_fee_paid_how']),
      land_holdings: O.LAND_CATEGORIES.map((c) => {
        const row = pick(land[c.value] || {}, LAND_COLS)
        return { ...row, quantity: row.quantity === '0' ? '' : row.quantity }
      }),
      asset_worth: O.ASSET_TITLES.map((t) => pick(worth[t.value] || {}, WORTH.map(([k]) => k))),
      education_loan: toBoolInput(app.education_loan),
    }
  },
  toPayload(form) {
    const vehicles = packRows(form.owns_transport === 'yes' ? form.vehicles : [], (r) => blank(r, VEHICLE_COLS),
      (r) => ({ ...r, engine_cc: toNumber(r.engine_cc) }))
    const land = packRows(form.land_holdings.map((r, i) => ({ ...r, category: O.LAND_CATEGORIES[i].value })),
      (r) => blank(r, LAND_COLS), (r) => ({ ...r, quantity: cell(r.quantity) }))
    return {
      payload: {
        owns_transport: fromBoolInput(form.owns_transport),
        vehicles: vehicles.payload,
        cattle_count: toNumber(form.cattle_count),
        cattle_kind: form.cattle_kind,
        land_holdings: land.payload,
        asset_worth: form.asset_worth.map((row, i) => ({
          title: O.ASSET_TITLES[i].value,
          ...Object.fromEntries(WORTH.map(([k]) => [k, cell(row[k])])),
        })),
        education_loan: fromBoolInput(form.education_loan),
        education_loan_details: form.education_loan_details,
        other_financing: form.other_financing,
        admission_fee_paid_how: form.admission_fee_paid_how,
      },
      remap: (e) => remapRowErrors(remapRowErrors(e, 'vehicles', vehicles.origin), 'land_holdings', land.origin),
    }
  },
  Fields({ form, set, errors, app, disabled }) {
    const p = { form, set, errors, disabled }
    return (
      <>
        <h3>Transport (Q32)</h3>
        <div className="grid">
          <YesNo {...p} name="owns_transport" label="Does the family own any transport?" required />
        </div>
        {form.owns_transport === 'yes' && (
          <RowsTable rows={form.vehicles} setRows={(rows) => set('vehicles', rows)} disabled={disabled}
            errors={tableErrors(errors, 'vehicles')} addLabel="Add vehicle" max={10}
            makeRow={() => Object.fromEntries(VEHICLE_COLS.map((k) => [k, '']))}
            columns={[
              { name: 'transport_type', label: 'Type', type: 'select', options: O.TRANSPORT },
              { name: 'transport_type_other', label: 'If other, which', width: 110 },
              { name: 'make_model', label: 'Make / model', width: 130 },
              { name: 'engine_cc', label: 'Engine (CC)', type: 'number', width: 80 },
              { name: 'registration_no', label: 'Registration no.', width: 110 },
              { name: 'ownership_period', label: 'Ownership period', width: 110 },
            ]} />
        )}
        <h3>Cattle and land (Q33-34)</h3>
        <div className="grid">
          <Input {...p} name="cattle_count" label="Number of cattle" type="number" required hint="Enter 0 if none" />
          <Input {...p} name="cattle_kind" label="Kind of cattle" hint="e.g. 2 buffaloes, 1 cow" />
        </div>
        <RowsTable fixedLabels={O.LAND_CATEGORIES.map((c) => c.label)} rowHeader="Land / plot" disabled={disabled}
          rows={form.land_holdings} setRows={(rows) => set('land_holdings', rows)} errors={tableErrors(errors, 'land_holdings')}
          caption="Leave a row empty if you own none of that kind."
          columns={[
            { name: 'quantity', label: 'Qty', type: 'number', width: 60 },
            { name: 'size', label: 'Size', width: 90 },
            { name: 'location', label: 'Location (address)', width: 180 },
            { name: 'cultivable_area', label: 'Cultivable area', width: 100 },
            { name: 'yield_per_acre', label: 'Yield per acre', width: 100 },
          ]} />
        <h3>Assets worth, current market value (Q35)</h3>
        <RowsTable fixedLabels={O.ASSET_TITLES.map((t) => t.label)} rowHeader="Asset" disabled={disabled}
          rows={form.asset_worth} setRows={(rows) => set('asset_worth', rows)} errors={tableErrors(errors, 'asset_worth')}
          columns={WORTH.map(([name, label]) => ({ name, label: `${label} (Rs.)`, type: 'money', width: 100 }))} />
        <Totals rows={[['Total assets worth (35.1)', app.summary.asset_worth.total, true]]} />
        <h3>Financing (Q36-38)</h3>
        <div className="grid">
          <YesNo {...p} name="education_loan" label="Was any loan taken for your education?" required wide />
          {form.education_loan === 'yes' && (
            <TextArea {...p} name="education_loan_details" required
              label="Loan details and relationship with the relative / friend" rows={3} />
          )}
          <TextArea {...p} name="other_financing" label="Any source of financing other than loan" rows={2} hint="Optional" />
          <TextArea {...p} name="admission_fee_paid_how" label="How were the admission / first semester charges paid?" required rows={2} />
        </div>
      </>
    )
  },
}

// ---------- 8. Education and statement of purpose (Q39) ----------

const EDU_COLS = ['institute', 'monthly_fee', 'from_month', 'to_month', 'division', 'percentage', 'cgpa']
const PREV_COLS = ['institute', 'scholarship_name', 'total_amount', 'period', 'level']

const education = {
  key: 'education',
  title: 'Education',
  fromApp(app) {
    const byLevel = Object.fromEntries(app.education_records.map((r) => [r.level, r]))
    return {
      education_records: O.EDUCATION_LEVELS.map((l) => {
        const r = byLevel[l.value] || {}
        return { ...pick(r, EDU_COLS), from_month: toMonthInput(r.from_month), to_month: toMonthInput(r.to_month) }
      }),
      last_institution_monthly_fee: toInput(app.last_institution_monthly_fee),
      other_scholarships: toBoolInput(app.other_scholarships),
      previous_scholarships: app.previous_scholarships.map((r) => pick(r, PREV_COLS)),
      statement_of_purpose: toInput(app.statement_of_purpose),
    }
  },
  toPayload(form) {
    const records = packRows(form.education_records.map((r, i) => ({ ...r, level: O.EDUCATION_LEVELS[i].value })),
      (r) => blank(r, EDU_COLS), (r) => ({
        ...r,
        monthly_fee: toNumber(r.monthly_fee),
        from_month: fromMonthInput(r.from_month),
        to_month: fromMonthInput(r.to_month),
        percentage: r.percentage === '' ? null : r.percentage,
        cgpa: r.cgpa === '' ? null : r.cgpa,
      }))
    const previous = packRows(form.other_scholarships === 'yes' ? form.previous_scholarships : [],
      (r) => blank(r, PREV_COLS), (r) => ({ ...r, total_amount: toNumber(r.total_amount) }))
    return {
      payload: {
        education_records: records.payload,
        last_institution_monthly_fee: toNumber(form.last_institution_monthly_fee),
        other_scholarships: fromBoolInput(form.other_scholarships),
        previous_scholarships: previous.payload,
        statement_of_purpose: form.statement_of_purpose,
      },
      remap: (e) => remapRowErrors(remapRowErrors(e, 'education_records', records.origin), 'previous_scholarships', previous.origin),
    }
  },
  Fields({ form, set, errors, disabled }) {
    const p = { form, set, errors, disabled }
    return (
      <>
        <h3>Your educational record (Q39)</h3>
        <p className="field-hint">
          Secondary and Intermediate are required; fill Bachelors if you have one. For each, give a division, a
          percentage (0-100) or a CGPA (out of 4.00).
        </p>
        <RowsTable fixedLabels={O.EDUCATION_LEVELS.map((l) => l.label)} rowHeader="Level of study" disabled={disabled}
          rows={form.education_records} setRows={(rows) => set('education_records', rows)}
          errors={tableErrors(errors, 'education_records')}
          columns={[
            { name: 'institute', label: 'Name and location of institute', width: 200 },
            { name: 'monthly_fee', label: 'Fee per month (Rs.)', type: 'money', width: 90 },
            { name: 'from_month', label: 'From', type: 'month', width: 130 },
            { name: 'to_month', label: 'To', type: 'month', width: 130 },
            { name: 'division', label: 'Division', type: 'select', options: O.DIVISION },
            { name: 'percentage', label: '%age', width: 70 },
            { name: 'cgpa', label: 'CGPA', width: 70 },
          ]} />
        <div className="grid">
          <Input {...p} name="last_institution_monthly_fee" label="Monthly fee of the institution last attended (Rs.)" type="money" required />
          <YesNo {...p} name="other_scholarships" label="Have you ever received any other scholarship?" required />
        </div>
        {form.other_scholarships === 'yes' && (
          <RowsTable rows={form.previous_scholarships} setRows={(rows) => set('previous_scholarships', rows)} disabled={disabled}
            errors={tableErrors(errors, 'previous_scholarships')} addLabel="Add scholarship" max={10}
            caption="Upload proof of these scholarships in the documents step."
            makeRow={() => Object.fromEntries(PREV_COLS.map((k) => [k, '']))}
            columns={[
              { name: 'institute', label: 'Name of institute', width: 140 },
              { name: 'scholarship_name', label: 'Scholarship name', width: 140 },
              { name: 'total_amount', label: 'Total amount (Rs.)', type: 'money', width: 100 },
              { name: 'period', label: 'Total period', width: 100 },
              { name: 'level', label: 'Class / level', width: 100 },
            ]} />
        )}
        <TextArea {...p} name="statement_of_purpose" label="Statement of purpose: explain your suitability for this scholarship"
          required maxLength={3000} rows={7} hint="At least 100 characters." />
      </>
    )
  },
}

// ---------- 9. Undertaking (page 6) ----------

export const UNDERTAKING_TEXT = [
  'The information given in this application are true to the best of my knowledge and I understand that any incorrect information will result in the cancellation of this application. If any information given in this application is found incorrect or false after grant of financial assistance, the institute will stop further assistance and the student will have to refund all payment received and or penalty equal to total scholarship amount.',
  'AU reserves the right to use information given in this form for verification and other purposes.',
]

const undertaking = {
  key: 'undertaking',
  title: 'Undertaking',
  fromApp: (app) => ({ undertaking_accepted: Boolean(app.undertaking_accepted), undertaking_name: toInput(app.undertaking_name) }),
  toPayload: (form) => ({ payload: form, remap: keep }),
  Fields({ form, set, errors, app, disabled }) {
    const acceptError = errors?.undertaking_accepted && [].concat(errors.undertaking_accepted).join(' ')
    return (
      <>
        <ol className="undertaking">
          {UNDERTAKING_TEXT.map((t) => <li key={t}>{t}</li>)}
        </ol>
        <label className="checkbox">
          <input type="checkbox" checked={form.undertaking_accepted} disabled={disabled}
            onChange={(e) => set('undertaking_accepted', e.target.checked)} />
          I have read and accept this undertaking.
        </label>
        {acceptError && <p className="field-error">{acceptError}</p>}
        <div className="grid">
          <Input form={form} set={set} errors={errors} disabled={disabled} name="undertaking_name" required
            label="Type your full name" hint={`Exactly as in your personal details: ${app.applicant_name || ''}`} />
          <Display label="Date" value={app.undertaking_date || 'Recorded when you accept'} />
        </div>
        <p className="field-hint">
          Your parent or guardian signs on paper only: on the stamp-paper income declaration (Form 2).
        </p>
      </>
    )
  },
}

export const STEPS = [personal, household, parents, income, accommodation, expenses, assets, education, undertaking]
export const stepByKey = Object.fromEntries(STEPS.map((s) => [s.key, s]))
