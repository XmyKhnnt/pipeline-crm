(() => {
  const board = document.querySelector('#stage-board');
  if (!board || typeof Sortable === 'undefined') return;

  const csrfToken = () => {
    const item = document.cookie.split('; ').find((cookie) => cookie.startsWith('csrftoken='));
    return item ? decodeURIComponent(item.split('=')[1]) : '';
  };

  const postJson = async (url, payload) => {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('Could not save the board order.');
  };

  board.querySelectorAll('.card-list').forEach((list) => {
    new Sortable(list, {
      animation: 150,
      group: 'pipeline-cards',
      onEnd: async (event) => {
        const card = event.item;
        try {
          await postJson(card.dataset.moveUrl, {
            card_id: Number(card.dataset.cardId),
            destination_stage_id: Number(event.to.dataset.stageId),
            position: event.newIndex,
          });
        } catch (error) {
          window.location.reload();
        }
      },
    });
  });

  new Sortable(board, {
    animation: 150,
    draggable: '.kanban-column',
    handle: '.stage-drag-handle',
    onEnd: async () => {
      const stageIds = Array.from(board.querySelectorAll('.kanban-column')).map((column) =>
        Number(column.dataset.stageId),
      );
      try {
        await postJson(board.dataset.stageReorderUrl, { stage_ids: stageIds });
      } catch (error) {
        window.location.reload();
      }
    },
  });
})();
