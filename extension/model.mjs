export const FIELDS = ['name','phone','email','vacancy','reviewState','experience','education','skills','languages','notes'];
const LIMITS = {name:200,phone:80,email:200,vacancy:200,reviewState:200,experience:12000,education:12000,skills:6000,languages:3000,notes:12000};
export function profileIdentity(value) {
  try {
    const u = new URL(value);
    if (u.protocol !== 'https:' || u.hostname !== 'employers.indeed.com' || u.username || u.password || u.port || u.pathname.replace(/\/$/,'') !== '/candidates/view') return null;
    const one = key => u.searchParams.getAll(key).length === 1 && /^[a-f\d]{12}$/i.test(u.searchParams.get(key)) ? u.searchParams.get(key).toLowerCase() : '';
    const app = one('id'), job = one('legacyJobId');
    if (!app || !job) return null;
    return {id:`indeed:${job}:${app}`,url:`https://employers.indeed.com/candidates/view?id=${app}&legacyJobId=${job}`};
  } catch { return null; }
}
export function cleanFields(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Registro no válido.');
  const result = {};
  for (const key of FIELDS) {
    if (value[key] !== undefined && typeof value[key] !== 'string') throw Error('Un campo no es texto.');
    const text = (value[key] || '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g,'').trim();
    if (text.length > LIMITS[key]) throw Error(`El campo ${key} es demasiado largo; conserva el original y acórtalo.`);
    result[key] = text;
  }
  return result;
}
export function validateRecord(input) {
  const fields = cleanFields(input);
  if (!fields.name || !fields.vacancy) throw Error('Completa el nombre y la vacante.');
  const identity = profileIdentity(input.url);
  if (!identity || input.id !== identity.id) throw Error('Abre el perfil individual de una postulación de Indeed.');
  return {...identity,...fields};
}
export function saveRecord(current, input, {edit=false, now=new Date().toISOString()}={}) {
  const row = validateRecord(input);
  if (current && !edit) return {row:current,duplicate:true};
  if (edit && (!current || input.revision !== current.revision)) throw Error('Este registro cambió en otra ventana. Recarga la lista antes de editarlo.');
  return {row:{...row,revision:(current?.revision || 0)+1,createdAt:current?.createdAt || now,updatedAt:now},duplicate:false};
}
export function validateBackup(value) {
  if (value?.format !== 'bpower-candidatos-manual' || value.version !== 1 || !Array.isArray(value.records) || value.records.length > 5000) throw Error('Respaldo no válido.');
  const seen = new Set();
  return value.records.map(raw=>{
    const row = validateRecord(raw);
    if (seen.has(row.id)) throw Error('El respaldo contiene postulaciones repetidas.');
    seen.add(row.id);
    if (![raw.createdAt,raw.updatedAt].every(v=>typeof v==='string' && /^\d{4}-\d\d-\d\dT/.test(v) && Number.isFinite(Date.parse(v)))) throw Error('El respaldo tiene fechas no válidas.');
    return {...row,revision:1,createdAt:raw.createdAt,updatedAt:raw.updatedAt};
  });
}
