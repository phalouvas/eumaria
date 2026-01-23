frappe.ui.form.on('Patient Assessment', {
	refresh(frm) {
		// Auto-fill assessment_datetime with current datetime if empty
		if (!frm.doc.assessment_datetime && frm.doc.__islocal) {
			frm.set_value('assessment_datetime', frappe.datetime.now_datetime());
		}

		// Make annotated_body_map field read-only when empty (force canvas use), editable when exists (allow clear)
		frm.set_df_property('annotated_body_map', 'read_only', frm.doc.annotated_body_map ? 0 : 1);

		// Show annotate/edit buttons and a small preview if an image exists
		if (frm.doc.assessment_template) {
			frappe.db.get_value('Patient Assessment Template', frm.doc.assessment_template, ['requires_body_map', 'base_body_map']).then(r => {
				const cfg = r && r.message ? r.message : {};
				if (!cfg.requires_body_map) return;

				// Preview thumbnail next to the field (recreated on refresh)
				const fieldWrapper = frm.get_field('annotated_body_map').$wrapper;
				fieldWrapper.find('.body-map-preview').remove();
				if (frm.doc.annotated_body_map) {
					const preview = $(`
						<div class="body-map-preview" style="margin-top:8px;">
							<label class="control-label">${__('Current Body Map')}</label>
							<div>
								<img src="${frm.doc.annotated_body_map}" 
									style="max-width:240px; height:auto; border:1px solid #ddd; border-radius:4px; cursor:pointer;" 
									title="${__('Click to edit')}"
								/>
							</div>
						</div>
					`);
					preview.find('img').on('click', () => {
						show_body_map_dialog(frm, cfg.base_body_map);
					});
					fieldWrapper.append(preview);
				}

				// Buttons
				const label = frm.doc.annotated_body_map ? __('Edit Body Map') : __('Annotate Body Map');
				frm.add_custom_button(label, () => {
					show_body_map_dialog(frm, cfg.base_body_map);
				}, 'Actions');
			});
		}
	}
});

function show_body_map_dialog(frm, base_body_map_url) {
	// Load existing annotated image if present, otherwise use template's base image
	const imgPath = frm.doc.annotated_body_map || base_body_map_url || '';

	const d = new frappe.ui.Dialog({
		title: __('Annotate Body Map'),
		primary_action_label: __('Save'),
		primary_action: () => {
			const dataURL = canvas_to_png(dialogCanvas);
			if (!dataURL) {
				frappe.msgprint(__('No drawing detected.')); return;
			}
			attach_body_map(frm, dataURL).then(() => {
				d.hide(); frm.reload_doc();
			});
		}
	});

	// Make dialog nearly full-width on all devices while keeping responsiveness
	d.$wrapper.find('.modal-dialog').css({
		'max-width': '95vw',
		'width': '95vw'
	});

	const wrapper = d.$body.get(0);
	const toolbar = document.createElement('div');
	toolbar.style.marginBottom = '6px';
	toolbar.innerHTML = `
		<button class="btn btn-sm btn-secondary" data-action="clear">${__('Clear')}</button>
		<span style="margin-left: 15px; margin-right: 5px;">${__('Color')}:</span>
		<button class="btn btn-sm color-btn" data-color="#000000" style="background:#000000; width:30px; height:30px; border:2px solid #ddd; border-radius:4px; margin:0 2px;"></button>
		<button class="btn btn-sm color-btn" data-color="#0066cc" style="background:#0066cc; width:30px; height:30px; border:2px solid #ddd; border-radius:4px; margin:0 2px;"></button>
		<button class="btn btn-sm color-btn active" data-color="#d9534f" style="background:#d9534f; width:30px; height:30px; border:2px solid #333; border-radius:4px; margin:0 2px;"></button>
		<button class="btn btn-sm color-btn" data-color="#ffc107" style="background:#ffc107; width:30px; height:30px; border:2px solid #ddd; border-radius:4px; margin:0 2px;"></button>
		<button class="btn btn-sm color-btn" data-color="#ff6600" style="background:#ff6600; width:30px; height:30px; border:2px solid #ddd; border-radius:4px; margin:0 2px;"></button>
		<button class="btn btn-sm color-btn" data-color="#28a745" style="background:#28a745; width:30px; height:30px; border:2px solid #ddd; border-radius:4px; margin:0 2px;"></button>
	`;
	wrapper.appendChild(toolbar);

	let selectedColor = '#d9534f'; // Default red

	const dialogCanvas = document.createElement('canvas');
	dialogCanvas.style.border = '1px solid #ddd'; dialogCanvas.style.touchAction = 'none';
	dialogCanvas.style.width = '100%';
	wrapper.appendChild(dialogCanvas);

	const ctx = dialogCanvas.getContext('2d');

	const resizeCanvasToViewport = (img) => {
		const maxWidth = Math.floor(window.innerWidth * 0.9);
		const maxHeight = Math.floor(window.innerHeight * 0.85);

		if (img && img.width && img.height) {
			const imgRatio = img.width / img.height;
			let width = maxWidth;
			let height = Math.round(width / imgRatio);
			if (height > maxHeight) {
				height = maxHeight;
				width = Math.round(height * imgRatio);
			}
			dialogCanvas.width = width;
			dialogCanvas.height = height;
		} else {
			dialogCanvas.width = maxWidth;
			dialogCanvas.height = maxHeight;
		}
	};
	const bg = new Image();
	bg.onload = () => {
		resizeCanvasToViewport(bg);
		ctx.clearRect(0, 0, dialogCanvas.width, dialogCanvas.height);
		ctx.drawImage(bg, 0, 0, dialogCanvas.width, dialogCanvas.height);
	};
	bg.onerror = () => { /* Silently ignore missing image */ };
	bg.src = imgPath;

	let drawing = false; let last = null;
	const draw = (pt) => {
		if (!drawing) return;
		ctx.strokeStyle = selectedColor; ctx.lineWidth = 2; ctx.lineCap = 'round';
		ctx.beginPath();
		ctx.moveTo(last.x, last.y);
		ctx.lineTo(pt.x, pt.y);
		ctx.stroke();
		last = pt;
	};

	const getPt = (evt) => {
		const rect = dialogCanvas.getBoundingClientRect();
		const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
		const clientY = evt.touches ? evt.touches[0].clientY : evt.clientY;
		// Account for CSS scaling vs canvas intrinsic size to avoid pen offset
		const scaleX = dialogCanvas.width / rect.width;
		const scaleY = dialogCanvas.height / rect.height;
		const x = (clientX - rect.left) * scaleX;
		const y = (clientY - rect.top) * scaleY;
		return { x, y };
	};

	dialogCanvas.addEventListener('mousedown', (e) => { drawing = true; last = getPt(e); });
	dialogCanvas.addEventListener('mousemove', (e) => draw(getPt(e)));
	dialogCanvas.addEventListener('mouseup', () => { drawing = false; last = null; });
	dialogCanvas.addEventListener('mouseleave', () => { drawing = false; last = null; });
	dialogCanvas.addEventListener('touchstart', (e) => { drawing = true; last = getPt(e); e.preventDefault(); });
	dialogCanvas.addEventListener('touchmove', (e) => { draw(getPt(e)); e.preventDefault(); });
	dialogCanvas.addEventListener('touchend', () => { drawing = false; last = null; });

	toolbar.querySelector('[data-action="clear"]').addEventListener('click', () => {
		ctx.clearRect(0, 0, dialogCanvas.width, dialogCanvas.height);
		ctx.drawImage(bg, 0, 0, dialogCanvas.width, dialogCanvas.height);
	});

	// Color picker buttons
	toolbar.querySelectorAll('.color-btn').forEach(btn => {
		btn.addEventListener('click', () => {
			selectedColor = btn.getAttribute('data-color');
			// Update active state
			toolbar.querySelectorAll('.color-btn').forEach(b => b.style.border = '2px solid #ddd');
			btn.style.border = '2px solid #333';
		});
	});

	d.show();
}

function canvas_to_png(canvas) {
	try { return canvas.toDataURL('image/png'); } catch (e) { return null; }
}

function attach_body_map(frm, dataURL) {
	// dataURL like 'data:image/png;base64,....'
	const base64 = (dataURL || '').split(',')[1];
	if (!base64) return Promise.reject('Invalid image');

	const deleteExisting = () => {
		if (!frm.doc.annotated_body_map) return Promise.resolve();
		return frappe
			.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'File',
					fields: ['name'],
					filters: { file_url: frm.doc.annotated_body_map },
					limit_page_length: 1,
				},
				silent: true,
			})
			.then((r) => {
				const name = r && r.message && r.message[0] && r.message[0].name;
				if (!name) return null;
				return frappe.call({
					method: 'frappe.client.delete',
					args: { doctype: 'File', name },
					silent: true,
				});
			})
			.catch(() => {});
	};

	return deleteExisting().then(() =>
		frappe.call({
			method: 'frappe.client.attach_file',
			args: {
				filename: `body_map_${frm.doc.name}.png`,
				filedata: base64,
				decode_base64: 1,
				doctype: frm.doctype,
				docname: frm.doc.name,
				docfield: 'annotated_body_map',
				is_private: 1,
			},
		})
	);
}
