(() => {
  'use strict';
  const STORAGE_KEY = 'malaeb_bookings';
  const getBookings = () => {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(value) ? value : [];
    } catch (_) { return []; }
  };
  const saveBookings = bookings => localStorage.setItem(STORAGE_KEY, JSON.stringify(bookings));
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const arabicDate = value => {
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('ar-IQ', {weekday:'short', day:'numeric', month:'short', year:'numeric'}).format(date);
  };
  const arabicTime = value => {
    if (!value) return '';
    const [hours, minutes] = value.split(':').map(Number);
    const period = hours >= 12 ? 'م' : 'ص';
    return `${String(hours % 12 || 12).padStart(2,'0')}:${String(minutes).padStart(2,'0')} ${period}`;
  };
  const query = new URLSearchParams(location.search);
  const today = new Date();
  const todayValue = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  const nav = document.querySelector('.nav');
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('/sw.js').catch(() => {});
  const installButton = document.getElementById('install-app');
  let installPrompt;
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); installPrompt = event;
    if (installButton) installButton.classList.remove('is-hidden');
  });
  if (installButton) installButton.addEventListener('click', async () => {
    if (!installPrompt) return;
    installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; installButton.classList.add('is-hidden');
  });
  if (/iphone|ipad|ipod/i.test(navigator.userAgent) && !window.navigator.standalone) {
    const help = document.getElementById('install-help');
    if (help) help.textContent = 'على iPhone: افتح مشاركة Safari ثم «إضافة إلى الشاشة الرئيسية».';
  }
  const menuToggle = document.querySelector('.menu-toggle');
  if (menuToggle && nav) menuToggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  const form = document.getElementById('booking-form');
  if (form) {
    const dateInput = document.getElementById('booking-date');
    dateInput.min = todayValue;
    const requestedType = query.get('type');
    if (requestedType === '5' || requestedType === '7') {
      const choice = form.querySelector(`input[name="type"][value="${requestedType}"]`);
      if (choice) choice.checked = true;
    }
    const venueSelect = document.getElementById('stadium');
    const requestedVenue = query.get('venue');
    fetch('/api/venues').then(r => r.json()).then(data => {
      const venues = data.venues || [];
      venueSelect.innerHTML = '<option value="">اختار ملعبك</option>' + venues.map(v => `<option value="${escapeHTML(v.id)}">${escapeHTML(v.name)} — ${escapeHTML(v.city)}، ${escapeHTML(v.area)}</option>`).join('');
      if (requestedVenue) venueSelect.value = requestedVenue;
    }).catch(() => { venueSelect.innerHTML = '<option value="">تعذر تحميل الملاعب — شغّل التطبيق من الخادم</option>'; });
    form.addEventListener('submit', event => {
      event.preventDefault();
      const data = new FormData(form);
      const booking = {
        id: (globalThis.crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        name: String(data.get('name') || '').trim(),
        phone: String(data.get('phone') || '').trim(),
        type: String(data.get('type') || '5'),
        venue_id: String(data.get('venue_id') || ''),
        date: String(data.get('date') || ''),
        time: String(data.get('time') || ''),
        status: 'طلب حجز',
        createdAt: new Date().toISOString()
      };
      const error = document.getElementById('form-error');
      if (!booking.name || !booking.phone || !booking.venue_id || !booking.date || !booking.time) {
        error.textContent = 'تأكد من تعبئة كل الحقول المطلوبة.';
        error.classList.add('show');
        return;
      }
      if (!/^[+\d٠-٩۰-۹\s()-]{7,20}$/.test(booking.phone)) {
        error.textContent = 'اكتب رقم هاتف صحيح حتى يقدر الملعب يتواصل وياك.';
        error.classList.add('show');
        return;
      }
      if (booking.date < todayValue) {
        error.textContent = 'اختار تاريخ اليوم أو تاريخ جاي.';
        error.classList.add('show');
        return;
      }
      fetch('/api/bookings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({venue_id:booking.venue_id,name:booking.name,phone:booking.phone,pitch_type:booking.type,date:booking.date,time:booking.time})})
        .then(async response => { const result=await response.json(); if(!response.ok) throw new Error(result.error || 'تعذر إرسال الحجز.'); booking.status='بانتظار رد الملعب'; booking.stadium=venueSelect.options[venueSelect.selectedIndex].text; booking.booking_id=result.booking_id; const bookings=getBookings(); bookings.unshift(booking); saveBookings(bookings); form.classList.add('is-hidden'); document.getElementById('booking-title').textContent='وصل طلبك للملعب'; document.getElementById('booking-subtitle').textContent='الملعب يستلم طلبك ويحدث حالته بعد مراجعته.'; const success=document.getElementById('booking-success'); success.classList.remove('is-hidden'); document.getElementById('success-details').innerHTML=[booking.stadium,`${booking.type} ضد ${booking.type}`,arabicDate(booking.date),arabicTime(booking.time)].map(item=>`<span>${escapeHTML(item)}</span>`).join(''); })
        .catch(error => { document.getElementById('form-error').textContent=error.message; document.getElementById('form-error').classList.add('show'); });
    });
  }

  const mapList = document.querySelector('.map-list');
  if (mapList) fetch('/api/venues').then(r=>r.json()).then(data=>{
    mapList.innerHTML=(data.venues||[]).map(v=>`<article class="stadium-item"><div class="stadium-thumb">⚽</div><div class="stadium-info"><h3>${escapeHTML(v.name)}</h3><p>${escapeHTML(v.city)} · ${escapeHTML(v.area)}</p><div class="stadium-meta"><span>${(v.pitch_types||[]).map(t=>t==='5'?'خماسي':'سباعي').join(' و')}</span>${v.price?`<span>${escapeHTML(v.price)} د.ع / ساعة</span>`:''}</div><p>${escapeHTML(v.description||'')}</p></div><div class="stadium-actions"><span class="tag">مسجل</span><a class="small-button" href="booking.html?type=${escapeHTML((v.pitch_types||[])[0]||'5')}&venue=${escapeHTML(v.id)}">احجز هسه</a></div></article>`).join('');
  }).catch(()=>{});

  const list = document.getElementById('booking-list');
  if (list) {
    const bookings = getBookings();
    const empty = document.getElementById('empty-state');
    const count = document.getElementById('bookings-count');
    const search = document.getElementById('booking-search');
    const clear = document.getElementById('clear-bookings');
    const render = () => {
      const term = (search.value || '').trim().toLocaleLowerCase('ar');
      const filtered = bookings.filter(item => [item.name,item.phone,item.stadium,item.type,item.date].some(value => String(value || '').toLocaleLowerCase('ar').includes(term)));
      count.textContent = `${bookings.length} ${bookings.length === 1 ? 'حجز' : 'حجوزات'}`;
      list.innerHTML = filtered.map(item => `<article class="booking-row"><div><b>${escapeHTML(item.stadium || 'ملعب')}</b><small>${escapeHTML(item.type || '5')} ضد ${escapeHTML(item.type || '5')}</small></div><div><b>${escapeHTML(item.name)}</b><small>${escapeHTML(item.phone)}</small></div><div><b>${escapeHTML(arabicDate(item.date))}</b><small>${escapeHTML(arabicTime(item.time))}</small></div><span class="status">${escapeHTML(item.status || 'طلب حجز')}</span></article>`).join('');
      empty.classList.toggle('is-hidden', filtered.length > 0);
      const emptyTitle = document.getElementById('empty-title');
      const emptyText = document.getElementById('empty-text');
      if (bookings.length && !filtered.length) { emptyTitle.textContent = 'ما لقينا نتيجة'; emptyText.textContent = 'جرب تبحث باسم ثاني أو رقم الهاتف.'; }
      else { emptyTitle.textContent = 'بعد ما عندك حجوزات'; emptyText.textContent = 'اكتشف الملاعب واختار موعدك للمباراة الجاية.'; }
      clear.classList.toggle('is-hidden', bookings.length === 0);
    };
    search.addEventListener('input', render);
    clear.addEventListener('click', () => {
      if (!bookings.length) return;
      if (confirm('تمسح كل الحجوزات المحفوظة على هذا الجهاز؟')) { saveBookings([]); location.reload(); }
    });
    render();
  }
})();
