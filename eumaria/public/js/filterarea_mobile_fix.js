// Copyright (c) 2026, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

// Monkey patch to fix Frappe v16 mobile FilterArea.setup_mobile error
// Temporarily disable mobile detection during FilterArea creation

(function() {
	'use strict';
	
	let patchApplied = false;
	const maxAttempts = 100;
	let attempts = 0;
	
	const checkAndPatch = setInterval(function() {
		attempts++;
		
		if (window.frappe && frappe.views && frappe.views.BaseList) {
			const originalSetup = frappe.views.BaseList.prototype.setup_filter_area;
			
			if (originalSetup && !patchApplied) {
				patchApplied = true;
				clearInterval(checkAndPatch);
				
				// Replace setup_filter_area to temporarily disable mobile during FilterArea creation
				frappe.views.BaseList.prototype.setup_filter_area = function() {
					// Store original is_mobile function
					const originalIsMobile = frappe.is_mobile;
					
					// Temporarily make is_mobile return false during FilterArea construction
					frappe.is_mobile = function() { return false; };
					
					try {
						// Call original setup - FilterArea won't try to call setup_mobile
						originalSetup.call(this);
					} finally {
						// Restore original is_mobile
						frappe.is_mobile = originalIsMobile;
					}
					
					// Now manually call setup_mobile safely if we're actually on mobile
					if (this.filter_area && originalIsMobile && originalIsMobile()) {
						try {
							if (this.filter_area.$filter_list_wrapper && typeof this.filter_area.$filter_list_wrapper.hide === 'function') {
								this.filter_area.$filter_list_wrapper.hide();
							}
							
							if (this.page && typeof this.page.set_secondary_action === 'function') {
								this.page.set_secondary_action(
									__('Filters'),
									() => {
										if (this.filter_area.$filter_list_wrapper && typeof this.filter_area.$filter_list_wrapper.toggle === 'function') {
											this.filter_area.$filter_list_wrapper.toggle();
										}
									},
									{ icon: 'filter' }
								);
							}
						} catch (e) {
							// Silent failure
						}
					}
				};
				
				console.log('FilterArea mobile fix: Patched BaseList.setup_filter_area');
			}
		}
		
		if (attempts >= maxAttempts) {
			clearInterval(checkAndPatch);
			if (!patchApplied) {
				console.warn('FilterArea mobile fix: Could not find BaseList');
			}
		}
	}, 50);
})();
