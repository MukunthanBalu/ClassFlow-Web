// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(msg, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container') || (() => {
    const el = document.createElement('div');
    el.id = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── File upload drag-and-drop ─────────────────────────────────────────────────
document.querySelectorAll('.upload-area').forEach(area => {
  area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
  area.addEventListener('dragleave', () => area.classList.remove('dragover'));
  area.addEventListener('drop', e => {
    e.preventDefault(); area.classList.remove('dragover');
    const input = area.querySelector('input[type=file]');
    if (input && e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      area.querySelector('.chosen').textContent = e.dataTransfer.files[0].name;
    }
  });
  const input = area.querySelector('input[type=file]');
  if (input) {
    input.addEventListener('change', () => {
      const chosen = area.querySelector('.chosen');
      if (chosen) chosen.textContent = input.files[0]?.name || '';
    });
  }
});

// ── Student page: Check-in ────────────────────────────────────────────────────
const checkinBtn = document.getElementById('checkin-btn');
if (checkinBtn) {
  checkinBtn.addEventListener('click', async () => {
    const studentName = document.getElementById('student-name').value.trim();
    if (!studentName) { showToast('Please enter your name!', 'error'); return; }
    checkinBtn.disabled = true;
    const res = await fetch('/api/checkin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_name: studentName })
    });
    const data = await res.json();
    if (data.success) {
      showToast('✅ Attendance marked — you are Present!', 'success');
      const status = document.getElementById('checkin-status');
      if (status) { status.textContent = '✓ Marked Present'; status.className = 'checkin-status done'; }
    } else {
      showToast(data.error || 'Error checking in', 'error');
      checkinBtn.disabled = false;
    }
  });
}

// ── Student page: Assignment submission ───────────────────────────────────────
const submitForm = document.getElementById('submit-form');
if (submitForm) {
  submitForm.addEventListener('submit', async e => {
    e.preventDefault();
    const studentName = document.getElementById('student-name').value.trim();
    if (!studentName) { showToast('Please enter your name!', 'error'); return; }

    const btn = submitForm.querySelector('button[type=submit]');
    const progressWrap = document.getElementById('progress-wrap');
    const progressFill = document.getElementById('progress-fill');
    btn.disabled = true; btn.textContent = 'Uploading…';

    if (progressWrap) { progressWrap.style.display = 'block'; progressFill.style.width = '30%'; }

    const fd = new FormData(submitForm);
    fd.set('student_name', studentName);

    try {
      const res = await fetch('/api/submit', { method: 'POST', body: fd });
      if (progressFill) progressFill.style.width = '100%';
      const data = await res.json();
      if (data.success) {
        showToast('🎉 Assignment submitted successfully!', 'success');
        submitForm.reset();
        document.querySelectorAll('.chosen').forEach(el => el.textContent = '');
        if (progressWrap) setTimeout(() => { progressWrap.style.display = 'none'; progressFill.style.width = '0'; }, 600);
      } else {
        showToast(data.error || 'Submission failed', 'error');
        if (progressWrap) { progressWrap.style.display = 'none'; }
      }
    } catch (err) {
      showToast('Network error — try again', 'error');
      if (progressWrap) { progressWrap.style.display = 'none'; }
    }
    btn.disabled = false; btn.textContent = 'Submit Assignment';
  });
}

// ── Admin: Copy IP ────────────────────────────────────────────────────────────
const copyBtn = document.getElementById('copy-ip-btn');
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    const ip = document.getElementById('server-ip').textContent;
    navigator.clipboard.writeText(ip).then(() => showToast('URL copied to clipboard!', 'info'));
  });
}

// ── Admin: Attendance marking ─────────────────────────────────────────────────
document.querySelectorAll('.att-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const card = btn.closest('.att-student-card');
    const sid  = card.dataset.studentId;
    const date = document.getElementById('att-date-input')?.value;
    const status = btn.dataset.status;

    // Update UI immediately
    card.querySelectorAll('.att-btn').forEach(b => b.classList.remove('sel'));
    btn.classList.add('sel');

    await fetch('/api/attendance/mark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: parseInt(sid), date, status })
    });
  });
});

// ── Admin: Add student modal ──────────────────────────────────────────────────
const openModal  = document.getElementById('open-add-student');
const closeModal = document.getElementById('close-modal');
const modal      = document.getElementById('add-student-modal');
if (openModal && modal) {
  openModal.addEventListener('click', () => modal.classList.add('open'));
  closeModal?.addEventListener('click', () => modal.classList.remove('open'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });
}

const addStudentForm = document.getElementById('add-student-form');
if (addStudentForm) {
  addStudentForm.addEventListener('submit', async e => {
    e.preventDefault();
    const name = document.getElementById('new-name').value.trim();
    const roll = document.getElementById('new-roll').value.trim();
    if (!name) { showToast('Name is required', 'error'); return; }

    const res  = await fetch('/api/students/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, roll_number: roll })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Student added!', 'success');
      setTimeout(() => location.reload(), 800);
    } else {
      showToast(data.error || 'Error adding student', 'error');
    }
  });
}

// ── Admin: Delete student ─────────────────────────────────────────────────────
document.querySelectorAll('.delete-student-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm(`Remove "${btn.dataset.name}" from the class?`)) return;
    const res = await fetch(`/api/students/delete/${btn.dataset.id}`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('Student removed', 'info');
      btn.closest('.stu-card')?.remove();
    }
  });
});
