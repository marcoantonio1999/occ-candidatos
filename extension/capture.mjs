// Self-contained: injected only after the person clicks the extension's capture button.
// No requests, clicks, navigation, timers, hidden state or browser storage access.
export function captureOpenCandidate() {
  const u = new URL(location.href);
  const one = key => u.searchParams.getAll(key).length === 1 && /^[a-f\d]{12}$/i.test(u.searchParams.get(key)) ? u.searchParams.get(key).toLowerCase() : '';
  if (u.protocol!=='https:' || u.hostname!=='employers.indeed.com' || u.username || u.password || u.port || u.pathname.replace(/\/$/,'')!=='/candidates/view' || !one('id') || !one('legacyJobId')) throw Error('Abre primero el perfil individual de un candidato en Indeed. La extensión no abre perfiles por ti.');
  const visible = n => n && n.getClientRects().length>0 && getComputedStyle(n).visibility!=='hidden' && !n.closest('[hidden],[aria-hidden="true"]');
  const text = n => visible(n) ? n.innerText.trim() : '';
  const body = document.body.innerText;
  if (/verificación adicional requerida|additional verification required|verify you are human|verifica que eres humano|checking your browser|just a moment|cf-chl-widget/i.test(document.title+'\n'+body) || document.querySelector('iframe[src*="challenges.cloudflare.com"],#challenge-running,#challenge-form')) throw Error('La página solicita una verificación. No se agregó ningún candidato. El avance anterior permanece guardado.');
  const plates = [...document.querySelectorAll('[data-testid="name-plate-name-item"]')].filter(visible);
  if (plates.length!==1) throw Error('No se identificó un perfil único. Abre la postulación completa o usa el formulario manual.');
  const name = text(plates[0].querySelector('h2')) || text(plates[0]);
  if (!name || name.length>200 || name.includes('\n')) throw Error('No pudimos identificar el nombre con seguridad. Usa el formulario manual.');
  const header = plates[0].closest('header,section') || plates[0].parentElement;
  const dialogs = [...document.querySelectorAll('[role="dialog"],[role="tooltip"]')].filter(visible).filter(n=>text(n).split('\n').some(line=>line.trim()===`Llamar a ${name}`));
  const scopes = [header,...dialogs];
  const phones = new Set(), emails = new Set();
  for (const scope of scopes) {
    for (const link of scope.querySelectorAll('a[href^="tel:"]')) if (visible(link) && /^[+\d\s().-]{7,80}$/.test(text(link))) phones.add(text(link));
    for (const link of scope.querySelectorAll('a[href^="mailto:"]')) if (visible(link) && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text(link))) emails.add(text(link));
    const lines = text(scope).split('\n').map(s=>s.trim());
    const anchor = lines.indexOf(`Llamar a ${name}`);
    if (anchor>=0) for (const line of lines.slice(anchor+1,anchor+5)) if (/^\+?[\d\s().-]{7,80}$/.test(line) && line.replace(/\D/g,'').length>=7) phones.add(line);
  }
  const sections={experience:'',education:'',skills:'',languages:''};
  const profile=plates[0].closest('main,[role="main"]');
  if(profile){
    const norm=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
    const names={experience:['experiencia laboral','experiencia','work experience'],education:['educacion','formacion academica','education'],skills:['habilidades','skills'],languages:['idiomas','languages']};
    const headings=[...profile.querySelectorAll('h2,h3,h4,[role="heading"]')].filter(visible);
    for(const [key,labels] of Object.entries(names)){
      const matches=headings.filter(h=>labels.includes(norm(text(h))));
      if(matches.length!==1)continue;
      const parts=[];let node=matches[0].nextElementSibling;
      while(node&&!node.matches('h1,h2,h3,h4,[role="heading"]')&&!node.querySelector('h1,h2,h3,h4,[role="heading"]')){if(text(node))parts.push(text(node));node=node.nextElementSibling;}
      const value=parts.join('\n');
      if(value.length<=(key==='languages'?3000:key==='skills'?6000:12000))sections[key]=value;
    }
  }
  const canonical = `https://employers.indeed.com/candidates/view?id=${one('id')}&legacyJobId=${one('legacyJobId')}`;
  return {id:`indeed:${one('legacyJobId')}:${one('id')}`,url:canonical,name,
    phone:phones.size===1?[...phones][0]:'', email:emails.size===1?[...emails][0]:'',
    reviewState:'',...sections,notes:'',
    notice:'Solo se leyó el perfil abierto y sus secciones HTML visibles. Los datos no visibles quedan vacíos. La extensión no abre contactos, lee PDF incrustados ni descarga CV. Puedes completar los campos manualmente.'};
}
