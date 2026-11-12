let currentUser = null;
let currentFilter = 'all';
let allPostsCache = [];

function showBanner(msg, isError = false) {
    const b = document.getElementById('banner');
    b.innerText = msg;
    b.style.background = isError ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #10b981, #059669)';
    b.style.display = 'block';
    setTimeout(() => { b.style.display = 'none'; }, 4000);
}

function hideBanner() {
    document.getElementById('banner').style.display = 'none';
}

function togglePassword(fieldId, btn) {
    const input = document.getElementById(fieldId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerText = '🙈';
    } else {
        input.type = 'password';
        btn.innerText = '👁️';
    }
}

function toggleAuthMode(mode) {
    const loginBtn = document.getElementById('tab-login-btn');
    const regBtn = document.getElementById('tab-register-btn');
    const loginForm = document.getElementById('login-form');
    const regForm = document.getElementById('register-form');

    if (mode === 'login') {
        loginBtn.classList.add('active-tab');
        regBtn.classList.remove('active-tab');
        loginForm.style.display = 'block';
        regForm.style.display = 'none';
    } else {
        regBtn.classList.add('active-tab');
        loginBtn.classList.remove('active-tab');
        regForm.style.display = 'block';
        loginForm.style.display = 'none';
    }
}

function showForgotPasswordModal() {
    document.getElementById('reset-section').style.display = 'none';
    document.getElementById('forgot-email-input').value = '';
    document.getElementById('forgot-modal').style.display = 'flex';
}

function closeForgotPasswordModal() {
    document.getElementById('forgot-modal').style.display = 'none';
}

async function submitForgotPasswordRequest() {
    const email = document.getElementById('forgot-email-input').value.trim();
    if (!email || !email.includes('@')) {
        showBanner("Please enter a valid Gmail address.", true);
        return;
    }
    try {
        const res = await fetch('/api/forgot-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (res.ok) {
            showBanner(data.message || "Reset code sent to your Gmail inbox!");
            document.getElementById('reset-section').style.display = 'block';
        } else {
            showBanner(data.detail || "Failed to send reset code.", true);
        }
    } catch (e) {
        showBanner("Network error connecting to server.", true);
    }
}

async function submitNewPassword() {
    const email = document.getElementById('forgot-email-input').value.trim();
    const code = document.getElementById('reset-code-input').value.trim();
    const new_password = document.getElementById('reset-newpass-input').value.trim();

    if (!code || !new_password) {
        showBanner("Please fill in both the code and new password.", true);
        return;
    }

    try {
        const res = await fetch('/api/reset-password', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email, code, new_password })
        });
        const data = await res.json();
        if (res.ok) {
            showBanner("Password successfully reset! You can now login.");
            closeForgotPasswordModal();
        } else {
            showBanner(data.detail || "Password reset failed.", true);
        }
    } catch (e) {
        showBanner("Server error during password reset.", true);
    }
}

async function requestOTP() {
    const contact = document.getElementById('reg-gmail').value.trim();
    if (!contact || !contact.includes('@')) {
        showBanner("Please enter a valid Gmail address first.", true);
        return;
    }
    try {
        const res = await fetch('/api/send-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ contact })
        });
        const data = await res.json();
        if (res.ok) {
            showBanner("Verification code dispatched to your Gmail inbox!");
            document.getElementById('reg-code').value = data.code; // Auto-fills for convenience if needed
        } else {
            showBanner(data.detail || "Failed to send code.", true);
        }
    } catch (e) {
        showBanner("Network error connecting to server.", true);
    }
}

async function handleRegister() {
    const payload = {
        name: document.getElementById('reg-name').value.trim(),
        username: document.getElementById('reg-username').value.trim(),
        gmail: document.getElementById('reg-gmail').value.trim(),
        phone: document.getElementById('reg-phone').value.trim(),
        password: document.getElementById('reg-pass').value,
        gender: document.getElementById('reg-gender').value,
        age: parseInt(document.getElementById('reg-age').value) || 16,
        grade: document.getElementById('reg-grade').value.trim(),
        school: document.getElementById('reg-school').value.trim(),
        code: document.getElementById('reg-code').value.trim()
    };

    if (!payload.name || !payload.username || !payload.gmail || !payload.password || !payload.code) {
        showBanner("Please fill in all required fields including the verification code.", true);
        return;
    }

    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            showBanner("Registration successful! Please login.");
            toggleAuthMode('login');
        } else {
            showBanner(data.detail || "Registration failed.", true);
        }
    } catch (e) {
        showBanner("Server error during registration.", true);
    }
}

async function handleLogin() {
    const contact = document.getElementById('login-contact').value.trim();
    const password = document.getElementById('login-pass').value;

    if (!contact || !password) {
        showBanner("Please enter your login details and password.", true);
        return;
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ contact, password })
        });
        const data = await res.json();
        if (res.ok) {
            currentUser = data.user;
            document.getElementById('auth-container').style.display = 'none';
            document.getElementById('main-body').classList.remove('auth-page-body');
            document.getElementById('sticky-nav').style.display = 'flex';
            document.getElementById('app-container').style.display = 'block';
            switchTab('subjects');
            loadPosts();
            updateProfileUI();
            showBanner(`Welcome back, ${currentUser.name}!`);
        } else {
            showBanner(data.detail || "Login failed.", true);
        }
    } catch (e) {
        showBanner("Network error during login.", true);
    }
}

function logout() {
    currentUser = null;
    document.getElementById('auth-container').style.display = 'block';
    document.getElementById('main-body').classList.add('auth-page-body');
    document.getElementById('sticky-nav').style.display = 'none';
    document.getElementById('app-container').style.display = 'none';
    document.querySelectorAll('.app-section').forEach(s => s.style.display = 'none');
    showBanner("Logged out successfully.");
}

function switchTab(tabName) {
    const sections = ['subjects', 'feed', 'lounge', 'wallet', 'profile'];
    sections.forEach(s => {
        document.getElementById(`sec-${s}`).style.display = (s === tabName) ? 'block' : 'none';
    });
    if (tabName === 'lounge') updateLoungeUI();
}

function openSubject(subjectName) {
    const box = document.getElementById('subject-detail-view');
    box.style.display = 'block';
    box.innerHTML = `<h3>📚 ${subjectName} Curriculum Module</h3>
        <p>Accessing Ethiopian national curriculum units, chapter summaries, and interactive revision quizzes for ${subjectName}.</p>
        <button onclick="showBanner('Interactive quiz package loaded successfully!')">Start Unit Quiz</button>`;
}

async function loadPosts() {
    try {
        const res = await fetch('/api/posts');
        const data = await res.json();
        allPostsCache = data.posts;
        renderFeed();
    } catch (e) {
        console.error("Failed to load feed posts");
    }
}

function filterFeed(type) {
    currentFilter = type;
    ['all', 'photo', 'video', 'audio', 'text'].forEach(t => {
        const btn = document.getElementById(`filt-${t}`);
        if (btn) btn.classList.toggle('active-filter', t === type);
    });
    renderFeed();
}

function renderFeed() {
    const stream = document.getElementById('feed-stream');
    stream.innerHTML = '';
    
    const filtered = allPostsCache.filter(p => currentFilter === 'all' || p.type === currentFilter);
    if (filtered.length === 0) {
        stream.innerHTML = '<p style="text-align:center; color:#aaa; padding: 40px;">No posts found in this feed category.</p>';
        return;
    }

    filtered.forEach(p => {
        const liked = p.likes.includes(currentUser.username);
        const card = document.createElement('div');
        card.className = 'tiktok-post-card';
        if (p.mediaUrl && p.type === 'photo') {
            card.style.backgroundImage = `url('${p.mediaUrl}')`;
        } else {
            card.style.background = '#1a1a1a';
        }

        let mediaElement = '';
        if (p.mediaUrl) {
            if (p.type === 'video') {
                mediaElement = `<video class="tiktok-media-element" src="${p.mediaUrl}" autoplay loop muted controls></video>`;
            } else if (p.type === 'audio') {
                mediaElement = `<audio controls style="width:100%; margin:10px 0;"><source src="${p.mediaUrl}"></audio>`;
            }
        }

        card.innerHTML = `
            ${mediaElement}
            <div class="tiktok-overlay-info">
                <h3>@${p.username}</h3>
                <h4 style="margin:5px 0; color:#ffd700;">${p.title}</h4>
                <p style="font-size:14px; max-height:80px; overflow-y:auto;">${p.content}</p>
            </div>
            <div class="tiktok-sidebar-actions">
                <button class="action-btn-circle" onclick="likePost(${p.id})"><i class="fas fa-heart" style="color:${liked ? '#ef4444' : '#fff'}"></i></button>
                <span style="font-size:12px; font-weight:bold;">${p.likes.length}</span>

                <button class="action-btn-circle" onclick="openCommentsModal(${p.id})"><i class="fas fa-comment"></i></button>
                <span style="font-size:12px; font-weight:bold;">${p.comments ? p.comments.length : 0}</span>

                <button class="action-btn-circle" onclick="sharePostItem('${p.title}')"><i class="fas fa-share"></i></button>
            </div>
        `;
        stream.appendChild(card);
    });
}

async function publishPost() {
    const title = document.getElementById('post-title').value;
    const type = document.getElementById('post-type').value;
    const content = document.getElementById('post-content').value;
    const fileInput = document.getElementById('post-file');

    if (!title || !content) {
        showBanner("Please fill in title and content.", true);
        return;
    }

    const formData = new FormData();
    formData.append('username', currentUser.username);
    formData.append('title', title);
    formData.append('type', type);
    formData.append('content', content);
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }

    try {
        const res = await fetch('/api/posts', {
            method: 'POST',
            body: formData
        });
        if (res.ok) {
            showBanner("Post published successfully!");
            document.getElementById('post-title').value = '';
            document.getElementById('post-content').value = '';
            fileInput.value = '';
            loadPosts();
        } else {
            showBanner("Failed to publish post.", true);
        }
    } catch (e) {
        showBanner("Server connection error during posting.", true);
    }
}

async function likePost(postId) {
    try {
        const res = await fetch('/api/posts/like', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ postId, username: currentUser.username })
        });
        if (res.ok) loadPosts();
    } catch (e) {
        console.error("Like error");
    }
}

function openCommentsModal(postId) {
    let commentText = prompt("Add a comment to this post:");
    if (!commentText) return;

    fetch('/api/posts/comment', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ postId: postId, username: currentUser.username, text: commentText })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showBanner("Comment added successfully!");
            loadPosts();
        }
    });
}

function sharePostItem(title) {
    if (navigator.share) {
        navigator.share({ title: 'R-Sniper Hub Post', text: title, url: window.location.href });
    } else {
        navigator.clipboard.writeText(window.location.href);
        showBanner("Post link copied to clipboard!");
    }
}

function updateLoungeUI() {
    const count = currentUser.followers.length;
    document.getElementById('lounge-follower-count').innerText = count;
    const btn = document.getElementById('go-live-btn');
    if (count >= 5) {
        btn.style.background = '#10b981';
        btn.innerText = 'Go Live Now (Criteria Met)';
    } else {
        btn.style.background = '#ef4444';
        btn.innerText = `Need ${5 - count} More Followers to Go Live`;
    }
    loadLiveRequests();
}

function triggerGoLive() {
    if (currentUser.followers.length < 5) {
        showBanner("Criteria not met: You need at least 5 followers to host a live study lounge.", true);
    } else {
        showBanner("Live study room initialized! Broadcasting to peers...");
        document.getElementById('host-approval-panel').style.display = 'block';
    }
}

async function requestLiveJoin() {
    let hostName = prompt("Enter the host's username to request joining their live stream:");
    if (!hostName) return;

    try {
        const res = await fetch('/api/live/request-join', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ host_username: hostName, username: currentUser.username })
        });
        if (res.ok) {
            showBanner("Join request sent to host successfully!");
        } else {
            showBanner("Failed to send join request.", true);
        }
    } catch (e) {
        showBanner("Network error.", true);
    }
}

async function loadLiveRequests() {
    try {
        const res = await fetch(`/api/live/requests/${currentUser.username}`);
        const data = await res.json();
        const listDiv = document.getElementById('requests-list');
        if (!listDiv) return;
        listDiv.innerHTML = '';
        if (data.requests.length === 0) {
            listDiv.innerHTML = '<small style="color:#888;">No pending requests.</small>';
            return;
        }
        data.requests.forEach(r => {
            listDiv.innerHTML += `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px; background:#222; padding:8px; border-radius:4px;">
                    <span>@${r.username}</span>
                    <button onclick="approveLiveJoin(${r.id})" style="background:#10b981; padding:4px 10px; width:auto; font-size:12px;">Approve</button>
                </div>
            `;
        });
    } catch (e) {
        console.error("Error loading live requests");
    }
}

async function approveLiveJoin(reqId) {
    const res = await fetch('/api/live/approve-join', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ request_id: reqId })
    });
    if (res.ok) {
        showBanner("User approved to join live stream!");
        loadLiveRequests();
    }
}

function updateProfileUI() {
    document.getElementById('prof-name').innerText = currentUser.name;
    document.getElementById('prof-username').innerText = currentUser.username;
    document.getElementById('prof-grade').innerText = currentUser.grade;
    document.getElementById('prof-school').innerText = currentUser.school;
    document.getElementById('prof-bio-text').innerText = currentUser.bio || "No bio yet.";
    document.getElementById('prof-privacy-text').innerText = currentUser.privacy || "Public";
    document.getElementById('prof-followers-cnt').innerText = currentUser.followers.length;
    document.getElementById('prof-following-cnt').innerText = currentUser.following.length;
    document.getElementById('wallet-balance').innerText = `${currentUser.wallet.toFixed(2)} ETB`;
}

function openSettingsModal() {
    document.getElementById('settings-bio').value = currentUser.bio || "";
    document.getElementById('settings-privacy').value = currentUser.privacy || "public";
    document.getElementById('settings-modal').style.display = 'flex';
}

function closeSettingsModal() {
    document.getElementById('settings-modal').style.display = 'none';
}

async function saveProfileSettings() {
    const bio = document.getElementById('settings-bio').value;
    const privacy = document.getElementById('settings-privacy').value;

    try {
        const res = await fetch('/api/user/update-profile', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username: currentUser.username, bio, privacy })
        });
        if (res.ok) {
            currentUser.bio = bio;
            currentUser.privacy = privacy;
            updateProfileUI();
            closeSettingsModal();
            showBanner("Profile updated successfully!");
        }
    } catch (e) {
        showBanner("Failed to update profile.", true);
    }
}

async function searchRegisteredUsers(query) {
    const resBox = document.getElementById('searched-profile-result');
    if (!query.trim()) {
        resBox.innerHTML = '';
        return;
    }
    try {
        const res = await fetch(`/api/search-users?query=${encodeURIComponent(query)}`);
        const data = await res.json();
        resBox.innerHTML = '';
        if (data.users.length === 0) {
            resBox.innerHTML = '<small style="color:#aaa;">No registered users found.</small>';
            return;
        }
        data.users.forEach(u => {
            if (u.username === currentUser.username) return;
            const isFollowing = currentUser.following.includes(u.username);
            resBox.innerHTML += `
                <div style="background:#222; padding:10px; border-radius:6px; margin-top:8px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong>@${u.username}</strong><br>
                        <small style="color:#aaa;">${u.name || ''} (${u.followers_count} followers)</small>
                    </div>
                    <button onclick="toggleFollow('${u.username}')" style="background:${isFollowing ? '#ef4444' : '#10b981'}; width:auto; padding:5px 12px; font-size:12px;">
                        ${isFollowing ? 'Unfollow' : 'Follow'}
                    </button>
                </div>
            `;
        });
    } catch (e) {
        console.error("Search error");
    }
}

async function toggleFollow(targetUsername) {
    try {
        const res = await fetch('/api/social/follow', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username: currentUser.username, target_username: targetUsername })
        });
        const data = await res.json();
        if (res.ok) {
            if (data.action === 'followed') {
                currentUser.following.push(targetUsername);
                showBanner(`Successfully followed @${targetUsername}`);
            } else {
                currentUser.following = currentUser.following.filter(u => u !== targetUsername);
                showBanner(`Unfollowed @${targetUsername}`);
            }
            updateProfileUI();
            searchRegisteredUsers(document.getElementById('search-profile-input').value);
        }
    } catch (e) {
        showBanner("Failed to update follow status.", true);
    }
}