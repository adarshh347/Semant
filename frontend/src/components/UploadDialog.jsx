// Shell-level upload surface. Upload used to be a form pinned above the archive;
// now it's an action (⌘K → "Upload an image", or the Archive's Upload button)
// that opens this Radix dialog. On success it broadcasts `semant:posts-changed`
// so the archive refreshes, and invalidates the posts cache.
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, useToast } from './ui';
import UploadForm from './UploadForm';

export default function UploadDialog() {
  const [open, setOpen] = useState(false);
  // HARNESS-003C. `semant:open-upload` may now carry a correlation id, and the dialog's only job
  // with it is to hand it to the form so the creation broadcast can be matched to the surface that
  // asked for it. Without this the round trip cannot close: `/inquiry` opens the shared dialog,
  // the form creates the post, and the resulting `semant:posts-created` carries no id — so the
  // inquiry cannot tell it apart from an upload the person started in the Archive, and correctly
  // ignores it. Callers that dispatch the bare event are unaffected; the id is simply empty.
  const [requestId, setRequestId] = useState('');
  const queryClient = useQueryClient();
  const { toast } = useToast();

  useEffect(() => {
    const onOpen = (event) => {
      setRequestId(String(event?.detail?.requestId || ''));
      setOpen(true);
    };
    window.addEventListener('semant:open-upload', onOpen);
    return () => window.removeEventListener('semant:open-upload', onOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        title="Add to the archive"
        description="Upload an image to read and write from."
        size="md"
      >
        <UploadForm
          requestId={requestId}
          onUploadSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['posts'] });
            window.dispatchEvent(new CustomEvent('semant:posts-changed'));
            toast({
              variant: 'success',
              title: 'Image added',
              description: 'It’s in the archive.',
            });
            setRequestId('');
            setOpen(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
