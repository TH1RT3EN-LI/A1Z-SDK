pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Item {
    id: root

    required property var theme
    required property var controller
    property bool armDraftPending: false
    property bool gripperDraftPending: false
    property bool configurationDraftPending: false
    readonly property bool motionDraftPending:
        root.armDraftPending || root.gripperDraftPending
    readonly property bool anyDraftPending:
        root.motionDraftPending || root.configurationDraftPending

    RowLayout {
        anchors.fill: parent
        spacing: root.theme.spacingM

        PageScrollView {
            id: diagnosticsScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0.54 * root.width
            ColumnLayout {
                width: diagnosticsScroll.availableWidth
                spacing: root.theme.spacingM

                PreflightPanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: implicitHeight
                    theme: root.theme
                    controller: root.controller
                }

                RosStackPanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: implicitHeight
                    theme: root.theme
                    controller: root.controller
                    anyDraftPending: root.anyDraftPending
                }

                MaintenancePanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: implicitHeight
                    theme: root.theme
                    controller: root.controller
                    armDraftPending: root.armDraftPending
                    gripperDraftPending: root.gripperDraftPending
                    anyDraftPending: root.anyDraftPending
                }
            }
        }

        DiagnosticLogPanel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredWidth: 0.46 * root.width
            theme: root.theme
            controller: root.controller
        }
    }
}
