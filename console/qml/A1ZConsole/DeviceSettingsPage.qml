pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root
    objectName: "deviceSettingsPage"

    required property var theme
    required property var controller
    property bool armDraftPending: false
    property bool gripperDraftPending: false
    readonly property bool controlTargetPending:
        root.armDraftPending || root.gripperDraftPending
    readonly property bool hasPendingDrafts:
        gravityPanel.gravityFactorDirty

    PageScrollView {
        id: settingsScroll

        anchors.fill: parent

        ColumnLayout {
            width: settingsScroll.availableWidth
            spacing: root.theme.spacingM

            ControlServicePanel {
                Layout.fillWidth: true
                Layout.preferredHeight: 205
                theme: root.theme
                controller: root.controller
                gravityFactor: gravityPanel.gravityFactorDraft
                controlTargetPending: root.controlTargetPending
                configurationDraftPending: root.hasPendingDrafts
            }

            GravityCompensationPanel {
                id: gravityPanel

                Layout.fillWidth: true
                Layout.preferredHeight: 190
                theme: root.theme
                controller: root.controller
                operationBlocked: root.controlTargetPending
            }
        }
    }
}
