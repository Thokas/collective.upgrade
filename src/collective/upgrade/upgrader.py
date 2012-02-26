from zope import interface
from zope import component

import transaction

from Products.CMFCore import interfaces as cmf_ifaces
from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.upgrade import _upgrade_registry

from collective.upgrade import interfaces
from collective.upgrade import utils


class Upgrader(utils.Upgrader):
    interface.implements(interfaces.IPortalUpgrader)
    component.adapts(cmf_ifaces.ISiteRoot)

    def __call__(self):
        self.portal = portal = self.context
        self.setup = getToolByName(portal, 'portal_setup')

        # May fix the profile version
        migration = getToolByName(portal, 'portal_migration')
        migration.getInstanceVersion()

        # Do the core plone upgrade first
        baseline = self.setup.getBaselineContextID()
        prof_type, profile_id = baseline.split('-', 1)
        self.upgradeProfile(profile_id)

        # Upgrade installed add-ons
        self.upgradeAddOns()

    def upgradeProfile(self, profile_id):
        upgrades = list(self.listUpgrades(profile_id))
        while upgrades:
            try:
                transaction.begin()
                self.doUpgrades(profile_id, upgrades)
                self.commit()
            except:
                self.logger.exception('Exception upgrading %r' % profile_id)
                transaction.abort()
                break
            upgrades = list(self.listUpgrades(profile_id))
        else:
            self.log('Finished upgrading %r profile' % profile_id)

    def listUpgrades(self, profile_id):
        for info in self.setup.listUpgrades(profile_id):
            if type(info) == list:
                for subinfo in info:
                    if subinfo['proposed']:
                        yield subinfo
            elif info['proposed']:
                yield info

    def doUpgrades(self, profile_id, steps_to_run):
        """Perform all selected upgrade steps.
        """
        step = None
        for step in steps_to_run:
            step = _upgrade_registry.getUpgradeStep(profile_id, step['id'])
            if step is not None:
                self.log("Running upgrade step %s for profile %s"
                         % (step.title, profile_id))
                step.doStep(self.setup)
                self.log("Ran upgrade step %s for profile %s"
                         % (step.title, profile_id))

        # We update the profile version to the last one we have reached
        # with running an upgrade step.
        if step and step.dest is not None and step.checker is None:
            self.log("Upgraded profile %r to %r" % (profile_id, step.dest))
            self.setup.setLastVersionForProfile(profile_id, step.dest)

    def upgradeAddOns(self):
